"""Complementos ao pywebview 6.2.1 no macOS para getUserMedia (R43).

O cocoa.py empacotado não implementa
webView:requestMediaCapturePermissionForOrigin:...; sem isso o WKWebView
nega ou fica parado no pedido de microfone.

Métodos adicionados depois da criação da classe NSObject não entram no
runtime Objective-C: por isso substituímos BrowserDelegate por uma subclasse.
"""
from __future__ import annotations

import sys

_PATCHED = False


def patch_cocoa_media_capture() -> bool:
    """Instala o delegate de captura. True se o patch foi aplicado."""
    global _PATCHED
    if _PATCHED:
        return True
    if sys.platform != "darwin":
        return False
    try:
        from webview.platforms import cocoa
        import WebKit  # type: ignore
    except Exception:
        return False

    Base = cocoa.BrowserView.BrowserDelegate

    class MediaBrowserDelegate(Base):
        def webView_requestMediaCapturePermissionForOrigin_initiatedByFrame_type_decisionHandler_(
            self, webview, origin, frame, media_type, decision_handler
        ):
            grant = getattr(WebKit, "WKPermissionDecisionGrant", 1)
            decision_handler(grant)

    cocoa.BrowserView.BrowserDelegate = MediaBrowserDelegate

    _orig_init = cocoa.BrowserView.__init__

    def _init_with_media(self, window):
        _orig_init(self, window)
        try:
            config = self.webview.configuration()
            prefs = config.preferences()
            for key in (
                "mediaDevicesEnabled",
                "mediaStreamEnabled",
                "peerConnectionEnabled",
                "_mediaDevicesEnabled",
            ):
                try:
                    prefs.setValue_forKey_(True, key)
                except Exception:
                    pass
            try:
                config.setMediaTypesRequiringUserActionForPlayback_(0)
            except Exception:
                pass
        except Exception:
            pass

    cocoa.BrowserView.__init__ = _init_with_media
    _PATCHED = True
    return True
