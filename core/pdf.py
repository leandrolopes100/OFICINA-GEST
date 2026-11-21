from html import escape

from reportlab.lib import colors

TEXTO_RODAPE = 'Oficina Gest - Sistema de Gestão · lopsystem.com.br'
URL_LOPSYSTEM = 'https://lopsystem.com.br'


def texto_seguro(valor):
    return escape(str(valor or ''), quote=False).replace('\r\n', '\n').replace('\n', '<br/>')


def desenhar_rodape(canvas, doc):
    canvas.saveState()
    canvas.setFont('Helvetica', 7.5)
    canvas.setFillColor(colors.HexColor('#6c757d'))
    largura_pagina = doc.pagesize[0]
    y = doc.bottomMargin / 2
    canvas.drawCentredString(largura_pagina / 2, y, TEXTO_RODAPE)
    largura_texto = canvas.stringWidth(TEXTO_RODAPE, 'Helvetica', 7.5)
    x0 = (largura_pagina - largura_texto) / 2
    canvas.linkURL(URL_LOPSYSTEM, (x0, y - 2, x0 + largura_texto, y + 8), relative=0)
    canvas.restoreState()
