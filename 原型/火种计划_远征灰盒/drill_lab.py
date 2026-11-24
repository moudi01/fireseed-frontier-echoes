"""Developer-only build-combination harness; never loads a player campaign."""
import argparse
from pathlib import Path
import time
from engine import BASE, Game, require
import drills


class DrillLab(Game):
    developer_drills = True

    @classmethod
    def create(cls, seed=11, save_path=None):
        # Prepare the ordinary starting roster only in a fresh in-memory fixture.
        source=Game.new_campaign(seed=seed)
        source.execute('quest commission CONFIRM')
        source.execute('tutorial recommend CONFIRM')
        source.s.update(developer_drill_only=True,debug_tainted=True)
        lab=cls(source.cat,source.s,save_path)
        lab.persist()
        return lab

    def dispatch(self, command, args):
        require(self.s.get('developer_drill_only'), '缺少开发试验标识。')
        require(command=='drill', '开发工具仅接受drill命令，不能推进正式周目。')
        return drills.handle(self,args)

    def describe(self):return drills.describe(self)


def main():
    parser=argparse.ArgumentParser(description='开发组合试验：独立测试档，不开放给玩家，不接收正常周目存档。')
    parser.add_argument('--seed',type=int,default=11)
    parser.add_argument('--load',type=Path,help='仅限本工具创建的测试档')
    args=parser.parse_args()
    try:
        path=BASE/'local/drill_lab'/str(time.time_ns())/'save.json'
        lab=DrillLab.load(args.load) if args.load else DrillLab.create(args.seed,path)
        print(lab.describe());print('开发测试档：',lab.save_path)
        while True:
            try:command=input('\ndev> ').strip()
            except (EOFError,KeyboardInterrupt):break
            if command=='quit':break
            if command in ('help','status'):print(lab.describe());continue
            try:print(lab.execute(command))
            except (ValueError,OSError) as exc:print('未执行：',exc)
        return 0
    except (ValueError,OSError) as exc:
        print('无法启动：',exc);return 1


if __name__=='__main__':raise SystemExit(main())
