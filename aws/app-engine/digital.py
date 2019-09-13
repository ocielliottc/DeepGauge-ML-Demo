# ******************************************************************
# Description: Draw digital style numbers on an image
#      Author: Chad Elliott
#        Date: 9/13/2019
# ******************************************************************

from PIL import ImageDraw

class Digital:
    line_width = 3
    color = (0,0,0)
    width  = 10
    height = 20
    space = 3
    __part = {'top': { 0,    2, 3,    5, 6, 7, 8, 9 },
              'ltv': { 0,          4, 5, 6,    8, 9 },
              'rtv': { 0, 1, 2, 3, 4,       7, 8, 9 },
              'mid': {       2, 3, 4, 5, 6,    8, 9 },
              'lbv': { 0,    2,          6,    8    },
              'rbv': { 0, 1,    3, 4, 5, 6, 7, 8, 9 },
              'bot': { 0,    2, 3,    5, 6,    8, 9 },
             }

    def drawHorizontal(draw, x, y, l):
        draw.line([x,y, x + l,y], fill=Digital.color, width=Digital.line_width)

    def drawVerticle(draw, x, y, l):
        draw.line([x,y, x,y + l], fill=Digital.color, width=Digital.line_width)

    def drawDash(draw, x, y):
        w = Digital.width
        h = Digital.height
        hh = h / 2
        Digital.drawHorizontal(draw, x, y + hh, w)
        return (w + Digital.line_width, h + Digital.line_width)

    def drawDecimal(draw, x, y):
        h = Digital.height
        draw.line([x-3,y+h, x-2,y+h],
                  fill=Digital.color, width=Digital.line_width)
        return (-Digital.space, Digital.height + Digital.line_width)

    def drawDigit(draw, x, y, num):
        if (num < 0 or num > 9):
            return (-Digital.space, -Digital.space)
        w = Digital.width
        h = Digital.height
        hh = h / 2
        if (num in Digital.__part['top']):
            Digital.drawHorizontal(draw, x, y, w)
        if (num in Digital.__part['ltv']):
            Digital.drawVerticle(draw, x, y, hh)
        if (num in Digital.__part['rtv']):
            Digital.drawVerticle(draw, x + w, y, hh)
        if (num in Digital.__part['mid']):
            Digital.drawHorizontal(draw, x, y + hh, w)
        if (num in Digital.__part['lbv']):
            Digital.drawVerticle(draw, x, y + hh, hh)
        if (num in Digital.__part['rbv']):
            Digital.drawVerticle(draw, x + w, y + hh, hh)
        if (num in Digital.__part['bot']):
            Digital.drawHorizontal(draw, x, y + h, w)
        return (w + Digital.line_width, h + Digital.line_width)

    def drawNumber(image, x, y, num):
        draw = ImageDraw.Draw(image)
        snum = num if (isinstance(num, str)) else str(num)
        for ch in snum:
            if (ch == ' '):
                dim = (Digital.width + Digital.line_width,
                       Digital.height + Digital.line_width)
            elif (ch == '-'):
                dim = Digital.drawDash(draw, x, y)
            elif (ch == '.'):
                dim = Digital.drawDecimal(draw, x, y)
            else:
                dim = Digital.drawDigit(draw, x, y, int(ch))
            x += dim[0] + Digital.space

