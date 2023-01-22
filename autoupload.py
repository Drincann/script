from asyncio.subprocess import STDOUT
import os
import time
import argparse
import asyncio


class asyncCounter:
    def __init__(self):
        self.count = 0

    async def __inc(self, sec):
        await asyncio.sleep(sec)
        self.count += 1

    async def __dec(self, sec):
        await asyncio.sleep(sec)
        self.count -= 1

    def inc(self, sec):
        asyncio.create_task(self.__inc(sec))

    def dec(self, sec):
        asyncio.create_task(self.__dec(sec))


async def main():
    argparser = argparse.ArgumentParser(description='Auto Commit')

    argparser.add_argument(
        '-d', '--dir', help='Repo directory to commit', required=True)
    argparser.add_argument(
        '-i', '--interval', help='Interval to commit', required=False, default=30, type=int)
    argparser.add_argument(
        '-t', '--time', help='Time to record commit', required=False, default=30, type=int)
    args = argparser.parse_args()
    counter = asyncCounter()
    os.chdir(os.path.abspath(args.dir))

    while True:
        os.system('clear')
        strtime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
        print(
            f"""
+----------------------------------------------------
| [time]: 
| {strtime}
|
| [status]:
| Work on {os.getcwd()}
| {counter.count} times commited over {args.time}min
| Sleep interval {args.interval}s
+----------------------------------------------------
"""
        )

        stdout = os.popen(f'git pull --rebase').read()
        stdout = os.popen(f'git add .').read()
        stdout = os.popen(f'git commit -m "auto upload {strtime}"').read()
        print(stdout)
        os.system(f'git push')

        if stdout.find('nothing to commit, working tree clean') == -1:
            counter.inc(0)
            counter.dec(args.time*60)

        await asyncio.sleep(args.interval)
asyncio.run(main())
