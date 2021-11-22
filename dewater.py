from typing import List
from PIL import Image
import argparse
import os


def change(rgbNew, input, output, silence: bool):
    i = 1
    j = 1
    img = Image.open(input)  # 读取系统的内照片
    # 使用Image模块的open()函数打开后，返回的图像对象的模式都是“RGB”。而对于灰度图像，不管其图像格式是PNG，还是BMP，或者JPG，打开后，其模式为“L”。
    print(f'file: {input}, size: {img.size} resolving...')  # 打印图片大小

    width = img.size[0]  # 长度
    height = img.size[1]  # 宽度
    for i in range(0, width):  # 遍历所有长度的点
        if not silence:
            print(f'file: {input}, row: {i + 1}/{width}')
        for j in range(0, height):  # 遍历所有宽度的点
            data = (img.getpixel((i, j)))  # 打印该图片的所有点
            # 寻找复合水印范围像素点
            if (data[0] >= 220 and data[0] <= 255 and data[1] >= 220 and data[1] <= 255 and data[1] >= 220 and data[1] <= 255):
                # 像素点的颜色改成白色
                img.putpixel((i, j), (rgbNew[0], rgbNew[1], rgbNew[2]))
    img = img.convert("RGB")  # 把图片强制转成RGB
    img.save(output)  # 保存修改像素点后的图片
    print(f'file: {input} resolved', end='\n\n')


def extname(filename):
    return os.path.splitext(filename)[1]


def shotname(filename):
    (_, tempfilename) = os.path.split(filename)
    (shotname, _) = os.path.splitext(tempfilename)
    return shotname


if __name__ == '__main__':
    argparser = argparse.ArgumentParser(description='dewater')

    argparser.add_argument(
        '-i', '--inputfile', help='Input files', required=True, type=str, nargs='+')
    argparser.add_argument(
        '-o', '--outputdir', help='Output dir default current dir', required=False, default=os.getcwd(), type=str)
    argparser.add_argument(
        '-s', '--silence', help='Silence default True', required=False, default=True, type=bool)
    args = argparser.parse_args()

    isDir = os.path.isdir(args.outputdir)
    isExists = os.path.exists(args.outputdir)
    if isExists:
        if not isDir:
            print(f'{args.outputdir} is not a dir')
            exit(1)
    else:
        os.makedirs(args.outputdir)
        print(f'output dir: {args.outputdir} created')

    print(args, end='\n\n')
    for filename in args.inputfile:
        change(
            (254, 254, 254),
            filename,
            os.path.join(os.path.abspath(args.outputdir),
                         f'{shotname(filename)}_new{extname(filename)}'),
            args.silence
        )
    print('done')
