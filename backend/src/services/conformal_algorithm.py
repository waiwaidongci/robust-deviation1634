import numpy as np

def upper_tail_p(calibration,test):
    try:cal=np.asarray(calibration,dtype=float);scores=np.asarray(test,dtype=float)
    except (TypeError,ValueError,OverflowError):raise ValueError("校准/测试分数须有限")
    if cal.ndim!=1 or scores.ndim!=1 or len(cal)<1 or len(scores)<1 or not np.isfinite(cal).all() or not np.isfinite(scores).all() or np.any(cal<0) or np.any(scores<0):raise ValueError("校准和测试须为非空有限非负平方距离")
    ge=len(cal)-np.searchsorted(np.sort(cal),scores,side='left')
    return {"p":((1+ge)/(len(cal)+1)).tolist(),"cal_ge_count":ge.tolist(),"m":len(cal),"resolution":1/(len(cal)+1),"tail":"上尾含等号：p=(1+#cal D²≥test D²)/(m+1)，同值保守"}

def holm_adjust(p_values):
    """Holm-Bonferroni 逐步下降族系校正，并列p共享同一校正结果。

    对n个原始p升序排列，第i位（1起）的Holm量为(n-i+1)*p_(i)，
    校正p为沿排名向前的累计最大值（cummax，与R p.adjust(method="holm")一致），截断到1。
    累计最大保证校正p单调，且与逐步下降检验在任意alpha下的拒绝集合完全一致；
    并列p取相同原始p，累计最大后自然得到相同校正p，不做人为随机破并列。
    返回与输入等长、同序的校正p、竞赛排名（并列同名次）与阈值乘子(n-r+1)。
    """
    p=np.asarray(p_values,dtype=float)
    if p.ndim!=1 or len(p)<1 or not np.isfinite(p).all() or np.any(p<0):raise ValueError("Holm校正须非空有限非负p序列")
    n=len(p)
    order=np.argsort(p,kind="mergesort")
    sorted_p=p[order]
    # 竞赛排名：相同原始p共享最小排名；乘子取该并列组首位的(n-r+1)，最保守
    ranks=np.empty(n,dtype=int)
    i=0
    while i<n:
        j=i+1
        while j<n and sorted_p[j]==sorted_p[i]:j+=1
        for k in range(i,j):ranks[order[k]]=i+1
        i=j
    multipliers=n-ranks+1
    # 逐步下降量按位置计算，再向前累计最大（cummax）实现标准Holm校正p
    step=np.arange(n)+1
    raw=(n-step+1)*sorted_p
    adj_sorted=np.minimum(1.0,np.maximum.accumulate(raw))
    adjusted=np.empty(n);adjusted[order]=adj_sorted
    return {"p_adj":adjusted.tolist(),"ranks":ranks.tolist(),"multipliers":multipliers.tolist(),"n":n,"method":"Holm-Bonferroni逐步下降：校正p=cummax(min(1,(n-i+1)p_(i)))，与R p.adjust(method='holm')一致；并列p共享排名与校正值，展示乘子为并列组(n-r+1)"}
