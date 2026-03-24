SUBSTACK_ARCHIVE_PRINT_CSS = r"""
@page {
  size: auto;
  margin: 0.55in 0.65in 0.70in 0.65in;
}

html,
body {
  background: #ffffff !important;
  color: #111111 !important;
  -webkit-print-color-adjust: exact !important;
  print-color-adjust: exact !important;
}

body {
  margin: 0 !important;
  padding: 0 !important;
}

#__archive_root__ {
  max-width: 760px;
  margin: 0 auto;
  padding: 24px 0 32px;
}

#__archive_root__ .archive-header {
  margin: 0 0 24px;
}

#__archive_root__ .image-link-expand,
#__archive_root__ .header-anchor-parent,
#__archive_root__ button,
#__archive_root__ [role="button"],
#__archive_root__ .subscription-widget-wrap,
#__archive_root__ .paywall-jump,
#__archive_root__ [data-testid="recommendation-footer"],
#__archive_root__ [data-testid="reaction-bar"],
#__archive_root__ [data-testid="post-footer"],
#__archive_root__ .subscribe-widget,
#__archive_root__ nav,
#__archive_root__ aside {
  display: none !important;
}

#__archive_root__ img {
  max-width: 100% !important;
  height: auto !important;
  page-break-inside: avoid !important;
  break-inside: avoid !important;
}

#__archive_root__ figure,
#__archive_root__ .captioned-image-container,
#__archive_root__ .file-embed-wrapper {
  page-break-inside: avoid !important;
  break-inside: avoid !important;
}

#__archive_root__ h1,
#__archive_root__ h2,
#__archive_root__ h3,
#__archive_root__ h4 {
  page-break-after: avoid !important;
  break-after: avoid !important;
}

#__archive_root__ a {
  color: inherit !important;
  text-decoration: underline;
}

#__archive_root__ .available-content,
#__archive_root__ .body,
#__archive_root__ .markup {
  overflow: visible !important;
}

#__archive_root__ .body.markup {
  overflow-wrap: anywhere;
}
"""
