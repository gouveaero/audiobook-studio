"""Gera na nuvem (Google Colab, via o CLI oficial `google-colab-cli`) e baixa os capítulos prontos.

  python -m studio.cloud run --project projects/meu-livro [--gpu A100] [--only 06,14]

Pré-requisitos: `uv tool install google-colab-cli` e login (`gcloud auth application-default login` com o escopo do
Colab; o CLI é chamado com `--auth adc`). Um plano com unidades de computação é necessário para A100/L4.

O que este módulo faz, com as lições aprendidas na prática:
  1. cria a sessão (503 = sem capacidade; tenta de novo até 6 vezes);
  2. instala o `omnivoice` na VM e envia book.json, voice/ e o pacote studio/;
  3. dispara `studio.generate` na VM em segundo plano (3 processos em GPU CUDA);
  4. acompanha e só baixa NN.m4a depois que o arquivo existe na VM (o gerador o renomeia só quando completo)
     e confere cada download com ffprobe. Arquivo parcial nunca é aceito;
  5. só encerra a VM (que gasta unidades mesmo parada) depois que todos os capítulos pedidos foram verificados.
Uma VM encerrada perde tudo o que estava nela: por isso a verificação vem antes do `stop`.
"""
import argparse, json, os, re, subprocess, sys, time

COLAB = ["colab", "--auth", "adc"]
SESSION = "audiobook"


def colab(*args, timeout=600, check=True):
    r = subprocess.run([*COLAB, *args], capture_output=True, text=True, timeout=timeout)
    out = "\n".join(l for l in (r.stdout + r.stderr).splitlines() if not l.startswith("[colab] A new version")
                    and not l.startswith("[colab] Run 'colab update") and "enable_update_check" not in l)
    if check and r.returncode:
        raise RuntimeError(out[-600:])
    return out


def vm_py(code, timeout=120, tries=3):
    """Código curto na VM. O `colab exec` às vezes pendura sem erro: tenta de novo antes de desistir.
    Nada longo passa por aqui (o kernel fica ocupado e as chamadas seguintes entram na fila); longo vai em nohup."""
    f = f"/tmp/_vm_{os.getpid()}.py"
    open(f, "w").write(code)
    for t in range(tries):
        try:
            return colab("exec", "-s", SESSION, "-f", f, "--timeout", str(timeout), timeout=timeout + 60)
        except subprocess.TimeoutExpired:
            if t == tries - 1:
                raise
            print(f"colab exec pendurou, tentando de novo ({t + 2}/{tries})"); time.sleep(10)


def vm_background(cmd, name, limit=1200):
    """Roda `cmd` em nohup na VM e espera o arquivo de término, consultando com chamadas curtas."""
    sh = f"({cmd}) > /content/{name}.log 2>&1; echo $? > /content/{name}.done"
    vm_py(f"import subprocess;subprocess.Popen({sh!r},shell=True,start_new_session=True);print('ok')", 60)
    t0 = time.time()
    while time.time() - t0 < limit:
        time.sleep(20)
        try:
            out = vm_py(f"import os;p='/content/{name}.done';print('@@'+(open(p).read().strip() if os.path.exists(p) else ''))", 60)
        except (RuntimeError, subprocess.TimeoutExpired):
            continue
        code = out.split("@@", 1)[-1].strip()
        if code:
            if code != "0":
                raise RuntimeError(f"{name} falhou na VM (código {code}); veja /content/{name}.log")
            return
    raise RuntimeError(f"{name} passou de {limit} s na VM")


def probe_ok(path):
    return subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                          capture_output=True).returncode == 0


def run(a):
    P = os.path.abspath(a.project)
    book = json.load(open(f"{P}/book.json"))["chapters"]
    want = a.only.split(",") if a.only else [c["id"] for c in book]
    leave = set(filter(None, a.leave.split(",")))  # capítulos reservados para este computador (studio.generate --only)
    todo = [i for i in want if i not in leave and not (os.path.exists(f"{P}/chapters/{i}.m4a") and probe_ok(f"{P}/chapters/{i}.m4a"))]
    if not todo:
        return print("Nada a gerar: todos os capítulos já existem e estão íntegros.")
    print(f"{len(todo)} capítulos para gerar na nuvem ({a.gpu})")
    for t in range(6):
        try:
            colab("new", "-s", SESSION, "--gpu", a.gpu); break
        except RuntimeError as e:
            print(f"sem capacidade (tentativa {t + 1}/6): {str(e)[-100:]}"); time.sleep(25)
    else:
        sys.exit("Não consegui alocar a GPU. Tente de novo em alguns minutos.")
    try:
        print("instalando o OmniVoice na VM...")
        vm_background("pip install -q omnivoice num2words", "pip")
        print("instalado")
        here = os.path.dirname(os.path.abspath(__file__))
        vm_py("import os;os.makedirs('/content/project/voice',exist_ok=True);os.makedirs('/content/studio',exist_ok=True)", 60)
        for f in ("book.json", "voice/ref.wav", "voice/ref.txt"):
            colab("upload", "-s", SESSION, f"{P}/{f}", f"/content/project/{f}")
        for f in os.listdir(here):
            if f.endswith(".py"):
                colab("upload", "-s", SESSION, f"{here}/{f}", f"/content/studio/{f}")
        # trava os capítulos que não foram pedidos, para os processos só pegarem os da lista
        lock = [c["id"] for c in book if c["id"] not in todo]
        vm_py("import os,subprocess\nos.makedirs('/content/project/work/locks',exist_ok=True)\n"
              f"for i in {lock!r}: open('/content/project/work/locks/'+i,'w').close()\n"
              "subprocess.Popen('cd /content && nohup python -m studio.generate --project /content/project > /content/gen.log 2>&1 &',shell=True)\nprint('lançado')", 60)
        os.makedirs(f"{P}/chapters", exist_ok=True)
        pending = set(todo)
        while pending:
            time.sleep(45)
            try:  # o `colab exec` às vezes pendura sem erro: pula a rodada em vez de morrer com a VM ligada
                out = vm_py("import subprocess,json,os\nsh=lambda c:subprocess.run(c,shell=True,capture_output=True,text=True).stdout\n"
                            "print('@@'+json.dumps({'ch':[f for f in os.listdir('/content/project/chapters') if f.endswith('.m4a') and '.tmp.' not in f],"
                            "'chunks':os.listdir('/content/project/work/chunks'),'gpu':int((sh('nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits').strip() or 0)),"
                            "'err':int(sh('grep -c Traceback /content/gen.log').strip() or 0)}))", 90)
            except (RuntimeError, subprocess.TimeoutExpired) as e:
                print("consulta à VM falhou, tento de novo:", str(e)[-120:]); continue
            try:
                st = json.loads(out.split("@@", 1)[1]); os.makedirs(f"{P}/work", exist_ok=True)
                json.dump({"chunks": st["chunks"], "gpu": st["gpu"]}, open(f"{P}/work/cloud_status.json", "w"))
            except Exception:
                continue
            ready = {f[:-4] for f in st["ch"] if re.fullmatch(r"\w+\.m4a", f)} & pending
            for i in sorted(ready):
                tmp = f"{P}/chapters/{i}.new.m4a"
                try:
                    colab("download", "-s", SESSION, f"/content/project/chapters/{i}.m4a", tmp, check=False)
                except subprocess.TimeoutExpired:
                    pass
                if os.path.exists(tmp) and probe_ok(tmp):
                    os.replace(tmp, f"{P}/chapters/{i}.m4a"); pending.discard(i); print(f"ok {i} ({len(todo) - len(pending)}/{len(todo)})")
                else:
                    print(f"download inválido de {i}, vai tentar de novo"); os.path.exists(tmp) and os.remove(tmp)
            if st["err"] and pending:
                print("O gerador na VM registrou erro (gen.log). Veja com: colab exec ... cat /content/gen.log"); break
    finally:
        if not a.keep and not (locals().get("pending")):
            try:  # a lista de trechos marcados (flagged) some com a VM
                os.makedirs(f"{P}/work", exist_ok=True)
                colab("download", "-s", SESSION, "/content/project/work/progress.jsonl", f"{P}/work/progress.cloud.jsonl", check=False)
            except subprocess.TimeoutExpired:
                print("não consegui baixar o progress.jsonl")
            colab("stop", "-s", SESSION, check=False); print("VM encerrada.")
        elif locals().get("pending"):
            print("VM MANTIDA (faltam capítulos). Encerre com: colab --auth adc stop -s", SESSION)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["run"]); ap.add_argument("--project", required=True)
    ap.add_argument("--gpu", default="A100", help="A100, L4, T4, H100")
    ap.add_argument("--only", default=""); ap.add_argument("--keep", action="store_true", help="não encerra a VM no fim")
    ap.add_argument("--leave", default="", help="ids que este computador gera ao mesmo tempo (a VM pula); escolha do fim do livro")
    run(ap.parse_args())
