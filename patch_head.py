#!/usr/bin/env python3
"""
patch_head.py — FinCodex landing page head patcher
====================================================
Injeta (idempotentemente) meta tags e scripts de tracking no <head>
estático do index.html exportado pelo Claude Design.

Uso:    python3 patch_head.py [caminho/do/index.html]
        (default: ./index.html)

Idempotência: o bloco injetado vive entre marcadores
<!-- fincodex:head start --> ... <!-- fincodex:head end -->.
Se os marcadores existem, o conteúdo entre eles é SUBSTITUÍDO
(atualizações neste script propagam no próximo deploy).
Se não existem, o bloco é inserido logo após </title>.
Rodar N vezes produz o mesmo resultado que rodar 1 vez.

Slots de tracking: preencha os IDs abaixo quando cada plataforma
for ativada. ID vazio = slot não injetado (zero JS desnecessário).
"""

import re
import sys
from pathlib import Path

# ---------------------------------------------------------------
# CONFIG — preencha conforme as plataformas forem ativadas
# ---------------------------------------------------------------
LINKEDIN_PARTNER_ID = ""   # LinkedIn Campaign Manager > Insight Tag  (ex: "1234567")
GA4_MEASUREMENT_ID  = "G-8X99WV5M9R"   # Google Analytics 4                       (ex: "G-XXXXXXXXXX")
META_PIXEL_ID       = ""   # Meta Events Manager                      (ex: "1234567890")

CANONICAL = "https://fincodex.com.br/"

# ---------------------------------------------------------------
# BLOCO 1 — Meta tags (sempre injetado)
# ---------------------------------------------------------------
META_BLOCK = """\
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="Consultoria FinOps multi-cloud no padrão FOCUS. Analisamos seu billing de Azure, AWS, GCP e OCI com agentes de IA e mostramos, com evidência rastreável até a fatura, onde sua empresa está desperdiçando dinheiro. Zero custo até a primeira economia comprovada.">
  <link rel="canonical" href="https://fincodex.com.br/">
  <meta property="og:type" content="website">
  <meta property="og:url" content="https://fincodex.com.br/">
  <meta property="og:site_name" content="FinCodex">
  <meta property="og:title" content="FinCodex — Sua nuvem esconde gastos que ninguém vê">
  <meta property="og:description" content="Diagnóstico FinOps multi-cloud com evidência rastreável até a fatura. Você só paga sobre a economia comprovada.">
  <meta property="og:image" content="https://fincodex.com.br/og-image.png">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:locale" content="pt_BR">
  <meta property="og:locale:alternate" content="en_US">
  <meta property="og:locale:alternate" content="es_ES">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="FinCodex — Sua nuvem esconde gastos que ninguém vê">
  <meta name="twitter:description" content="Diagnóstico FinOps multi-cloud com evidência rastreável até a fatura. Você só paga sobre a economia comprovada.">
  <meta name="twitter:image" content="https://fincodex.com.br/og-image.png">
  <link rel="icon" href="/favicon.svg" type="image/svg+xml">
  <link rel="apple-touch-icon" href="/apple-touch-icon.png">
  <meta name="theme-color" content="#1E0E05">"""

# ---------------------------------------------------------------
# BLOCO 2 — LinkedIn Insight Tag (injetado se PARTNER_ID definido)
# ---------------------------------------------------------------
LINKEDIN_BLOCK = """\
  <!-- LinkedIn Insight Tag -->
  <script type="text/javascript">
    _linkedin_partner_id = "{pid}";
    window._linkedin_data_partner_ids = window._linkedin_data_partner_ids || [];
    window._linkedin_data_partner_ids.push(_linkedin_partner_id);
  </script>
  <script type="text/javascript">
    (function(l) {{
      if (!l) {{ window.lintrk = function(a,b) {{ window.lintrk.q.push([a,b]) }}; window.lintrk.q = []; }}
      var s = document.getElementsByTagName("script")[0];
      var b = document.createElement("script");
      b.type = "text/javascript"; b.async = true;
      b.src = "https://snap.licdn.com/li.lms-analytics/insight.min.js";
      s.parentNode.insertBefore(b, s);
    }})(window.lintrk);
  </script>
  <noscript>
    <img height="1" width="1" style="display:none;" alt="" src="https://px.ads.linkedin.com/collect/?pid={pid}&fmt=gif" />
  </noscript>"""

# ---------------------------------------------------------------
# BLOCO 3 — Google Analytics 4 (injetado se MEASUREMENT_ID definido)
# ---------------------------------------------------------------
GA4_BLOCK = """\
  <!-- Google Analytics 4 -->
  <script async src="https://www.googletagmanager.com/gtag/js?id={mid}"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag() {{ dataLayer.push(arguments); }}
    gtag('js', new Date());
    gtag('config', '{mid}');
  </script>"""

# ---------------------------------------------------------------
# BLOCO 4 — Meta Pixel (injetado se PIXEL_ID definido)
# ---------------------------------------------------------------
META_PIXEL_BLOCK = """\
  <!-- Meta Pixel -->
  <script>
    !function(f,b,e,v,n,t,s){{if(f.fbq)return;n=f.fbq=function(){{n.callMethod?
    n.callMethod.apply(n,arguments):n.queue.push(arguments)}};if(!f._fbq)f._fbq=n;
    n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;
    t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}}(window,
    document,'script','https://connect.facebook.net/en_US/fbevents.js');
    fbq('init', '{pid}');
    fbq('track', 'PageView');
  </script>
  <noscript>
    <img height="1" width="1" style="display:none" src="https://www.facebook.com/tr?id={pid}&ev=PageView&noscript=1"/>
  </noscript>"""

# ---------------------------------------------------------------
# BLOCO 5 — Listener de clique no CTA (event delegation)
# Captura cliques em qualquer link para calendly.com, mesmo em
# elementos renderizados depois pelo bundle da SPA.
# Reporta a cada plataforma ativa. (Conversão "nível bronze".)
# ---------------------------------------------------------------
CTA_LISTENER_BLOCK = """\
  <!-- FinCodex: CTA click listener (event delegation, SPA-safe) -->
  <script>
    document.addEventListener('click', function (e) {{
      var a = e.target.closest && e.target.closest('a[href*="calendly.com"]');
      if (!a) return;
      try {{
        if (window.lintrk) {{ window.lintrk('track', {{ conversion_id: null }}); }}
        if (window.gtag)   {{ gtag('event', 'cta_calendly_click', {{ link_url: a.href }}); }}
        if (window.fbq)    {{ fbq('track', 'Lead'); }}
      }} catch (err) {{ /* nunca quebrar a navegação por causa de tracking */ }}
    }}, true);
  </script>"""

MARK_START = "<!-- fincodex:head start -->"
MARK_END   = "<!-- fincodex:head end -->"


def build_block() -> str:
    parts = [MARK_START, META_BLOCK]
    if LINKEDIN_PARTNER_ID:
        parts.append(LINKEDIN_BLOCK.format(pid=LINKEDIN_PARTNER_ID))
    if GA4_MEASUREMENT_ID:
        parts.append(GA4_BLOCK.format(mid=GA4_MEASUREMENT_ID))
    if META_PIXEL_ID:
        parts.append(META_PIXEL_BLOCK.format(pid=META_PIXEL_ID))
    if LINKEDIN_PARTNER_ID or GA4_MEASUREMENT_ID or META_PIXEL_ID:
        parts.append(CTA_LISTENER_BLOCK)
    parts.append("  " + MARK_END)
    return "\n".join(parts)


def patch(html: str) -> tuple[str, list[str]]:
    actions = []

    # --- 1. <html lang="pt-BR"> (idempotente) --------------------
    if re.search(r"<html\s+lang=", html):
        actions.append("lang: já presente, ok")
    else:
        html, n = re.subn(r"<html\s*>", '<html lang="pt-BR">', html, count=1)
        actions.append("lang: adicionado" if n else "lang: AVISO — tag <html> não encontrada no formato esperado")

    # --- 2. Bloco entre marcadores (substituir ou inserir) -------
    block = build_block()
    if MARK_START in html and MARK_END in html:
        pattern = re.escape(MARK_START) + r".*?" + re.escape(MARK_END)
        html = re.sub(pattern, block, html, count=1, flags=re.S)
        actions.append("bloco: atualizado (marcadores existentes)")
    else:
        # Remove eventual bloco legado inserido manualmente (evita duplicata):
        legacy = re.search(r"\n\s*<meta name=\"viewport\".*?<meta name=\"theme-color\"[^>]*>", html, re.S)
        if legacy and legacy.start() < html.find("</head>"):
            html = html[:legacy.start()] + html[legacy.end():]
            actions.append("bloco legado (edição manual): removido")
        m = re.search(r"</title>", html)
        if not m:
            actions.append("bloco: ERRO — </title> não encontrado")
            return html, actions
        insert_at = m.end()
        html = html[:insert_at] + "\n" + block + html[insert_at:]
        actions.append("bloco: inserido após </title>")

    return html, actions


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("index.html")
    if not path.exists():
        print(f"[patch_head] ERRO: {path} não encontrado")
        return 1
    original = path.read_text(encoding="utf-8")
    patched, actions = patch(original)
    for a in actions:
        print(f"[patch_head] {a}")
    if patched != original:
        path.write_text(patched, encoding="utf-8")
        print(f"[patch_head] {path} gravado ({len(patched):,} bytes)")
    else:
        print("[patch_head] nenhuma mudança necessária (idempotente)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
