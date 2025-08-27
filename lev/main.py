#!/usr/bin/env python3
import argparse

def lev(*, maxloss, sl, entry, marginrate):
    """
    计算在止损时亏损 maxloss 本金时所需的杠杆倍数
    """
    stop_loss_pct = abs(sl - entry) / entry
    return (maxloss / stop_loss_pct) / marginrate

def main():
    parser = argparse.ArgumentParser(description="计算在止损时亏损 maxloss 本金所需的杠杆倍数")
    parser.add_argument("-s", "--sl", type=float, required=True, help="止损价格")
    parser.add_argument("-e", "--entry", type=float, required=True, help="开仓价格")
    parser.add_argument("-l", "--maxloss", type=float, default=0.1, help="最大可接受亏损比例 (默认 0.1)")
    parser.add_argument("-m", "--marginrate", type=float, default=0.1, help="保证金占总资金比例 (默认 0.1)")

    args = parser.parse_args()

    leverage = lev(
        maxloss=args.maxloss,
        sl=args.sl,
        entry=args.entry,
        marginrate=args.marginrate
    )
    print(f"{leverage:.4f}")

if __name__ == "__main__":
    main()

