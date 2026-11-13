import numpy as np
from .robust_algorithm import fit_train,score_with_fit,training_scale,finite_matrix
from .conformal_algorithm import upper_tail_p,holm_adjust
from ..utils.fingerprint import fingerprint
VERSION='train-mcd-split-conformal-v2'
SINGLE_WINDOW='single_window'
FAMILY_WISE='family_wise_holm'
ERROR_CONTROL_MODES=(SINGLE_WINDOW,FAMILY_WISE)
def prepare_snapshot(snapshot):
    features=sorted(snapshot['features'],key=lambda f:f['position']);codes=[f['code'] for f in features]
    if len(features)!=4 or len(set(codes))!=4 or len({f['position'] for f in features})!=4:raise ValueError("须固定4个预定义且不重复的特征")
    rows=sorted(snapshot['windows'],key=lambda w:w['code'])
    if not 25<=len(rows)<=2000 or len({w['code'] for w in rows})!=len(rows):raise ValueError("窗口数25–2000且编号不得重复")
    if len({w['id'] for w in rows})!=len(rows):raise ValueError("窗口身份重复，拆分不可交叠")
    groups={s:[] for s in ['train','cal','test']}
    for w in rows:
        if w['split'] not in groups:raise ValueError("窗口角色仅train/cal/test")
        if set(w['values'])!=set(codes):raise ValueError("每窗口必须完整包含预定义4量，不得用test选择特征")
        groups[w['split']].append(w)
    if len(groups['train'])<20 or len(groups['cal'])<4 or len(groups['test'])<1:raise ValueError("严格拆分要求train≥20/cal≥4/test≥1")
    matrices={s:finite_matrix([[w['values'][c] for c in codes] for w in g],s) for s,g in groups.items()}
    training_scale(matrices['train'])
    return features,rows,groups,matrices

def _selection_reason(mode,p,p_adj,alpha,rank,multiplier,n,threshold):
    if mode==SINGLE_WINDOW:
        if p<=alpha:return f"单窗模式：原始p={p:.6g}≤预设α={alpha:g}，按单窗边际规则入选（不做整批校正）"
        if threshold==0:return f"单窗模式：原始p={p:.6g}>α={alpha:g}；α低于校准分辨率网格（可判定网格界为0），本窗不可能入选"
        return f"单窗模式：原始p={p:.6g}>预设α={alpha:g}（α网格可达界{threshold:.6g}），未入选；不证明无偏离"
    if p_adj<=alpha:return f"整批Holm模式：n={n}窗并列第{rank}名，乘子(n-r+1)={multiplier}，校正p={p_adj:.6g}≤α={alpha:g}，整批族系判定入选"
    return f"整批Holm模式：n={n}窗并列第{rank}名，乘子(n-r+1)={multiplier}，校正p={p_adj:.6g}>α={alpha:g}，整批族系判定未入选"

def analyze_deviation(snapshot,alpha=.05,seed=2026,error_control=FAMILY_WISE):
    if type(alpha) not in (int,float) or not np.isfinite(alpha) or not .01<=alpha<=.2:raise ValueError("预设alpha须在.01–.2之间")
    if error_control not in ERROR_CONTROL_MODES:raise ValueError("误报控制模式仅支持single_window或family_wise_holm")
    features,rows,groups,X=prepare_snapshot(snapshot);fit=fit_train(X['train'],seed);cal=score_with_fit(X['cal'],fit);test=score_with_fit(X['test'],fit);tail=upper_tail_p(cal,test)
    fit['raw_support_codes']=[w['code'] for w,m in zip(groups['train'],fit['raw_support_mask']) if m];fit['support_codes']=[w['code'] for w,m in zip(groups['train'],fit['support_mask']) if m]
    n=len(groups['test']);m=tail['m'];resolution=tail['resolution'];alpha_grid=np.floor(alpha*(m+1))/(m+1)
    if error_control==FAMILY_WISE:
        holm=holm_adjust(tail['p']);p_adj=holm['p_adj'];ranks=holm['ranks'];multipliers=holm['multipliers']
        selected=[bool(q<=alpha) for q in p_adj]
        correction_note=holm['method']
    else:
        p_adj=list(tail['p']);ranks=[1]*n;multipliers=[1]*n
        selected=[bool(p<=alpha) for p in tail['p']]
        correction_note="单窗模式不做整批校正：校正p等于原始p，排名与乘子占位为1；仅提供单个新窗口的边际误报控制，不控制整批族系错误率"
    scores=[]
    for w,d,p,q,k,sel,rk,mult in zip(groups['test'],test,tail['p'],p_adj,tail['cal_ge_count'],selected,ranks,multipliers):
        scores.append({"window":w,"d2":float(d),"p":float(p),"p_adj":float(q),"holm_rank":int(rk),"holm_multiplier":int(mult),"cal_ge_count":int(k),"selected":bool(sel),"selection_reason":_selection_reason(error_control,float(p),float(q),alpha,int(rk),int(mult),n,alpha_grid)})
    ecdf_values,ecdf_counts=np.unique(cal,return_counts=True);ecdf_y=np.cumsum(ecdf_counts)/len(cal)
    canonical={"study":snapshot['study'],"features":features,"windows":rows};fit_hash=fingerprint({"version":VERSION,"features":features,"train":[{"code":w['code'],"values":w['values']} for w in groups['train']],"seed":seed,"support_fraction":.8})
    selected_count=sum(x['selected'] for x in scores)
    # 校准分辨率说明：离散p网格下，alpha低于可判定网格时任何窗口都不可能入选
    if error_control==SINGLE_WINDOW:
        grid_note=f"单窗模式可判定α网格界为floor(α·(m+1))/(m+1)={alpha_grid:.6g}；最小p=分辨率{resolution:.6g}"
        no_select_note=(f"校准集仅{m}条，p分辨率1/(m+1)={resolution:.6g}；预设α={alpha:g}低于首个网格{resolution:.6g}（网格界{alpha_grid:.6g}=0），任何测试窗原始p都无法≤α，故无人入选。" if alpha_grid==0 else f"校准集{m}条，p分辨率{resolution:.6g}；α={alpha:g}对应网格界{alpha_grid:.6g}，本批原始p均高于该界，故无人入选（非系统故障）。")
    else:
        grid_note=f"整批Holm在离散p网格上判定；最小原始p={resolution:.6g}，经排名1的乘子n={n}放大后，最小校正p不低于min(1, n·分辨率)=min(1, {n*resolution:.6g})"
        no_select_note=(f"校准集仅{m}条，p分辨率1/(m+1)={resolution:.6g}；整批{n}窗经Holm后，最小校正p不低于min(1, {n}·{resolution:.6g})=min(1, {n*resolution:.6g})={min(1.0,n*resolution):.6g}，高于预设α={alpha:g}，网格分辨率不足，故无人入选。" if min(1.0,n*resolution)>alpha else f"校准集{m}条、整批{n}窗经Holm校正后，所有校正p均>α={alpha:g}，故无人入选（非系统故障）。")
    if selected_count>0:no_select_note=""
    return {"algorithm_version":VERSION,"error_control":error_control,"error_control_label":"单窗边际（旧规则，不做整批校正）" if error_control==SINGLE_WINDOW else "整批族系Holm校正","study":snapshot['study'],"features":features,"counts":{s:len(g) for s,g in groups.items()},"fit":fit,"fit_hash":fit_hash,"calibration":[{"window":w,"d2":float(d)} for w,d in zip(groups['cal'],cal)],"test":scores,"calibration_ecdf":[{"d2":float(d),"cdf":float(y)} for d,y in zip(ecdf_values,ecdf_y)],"alpha":alpha,"seed":seed,"selected_count":selected_count,"resolution":resolution,"alpha_grid_threshold":float(alpha_grid),"no_selection_note":no_select_note,"resolution_note":grid_note,"correction":correction_note,"tail":tail['tail'],"input_snapshot":canonical,"input_hash":fingerprint({"version":VERSION,"snapshot":canonical,"alpha":alpha,"seed":seed,"support_fraction":.8,"error_control":error_control}),"assumptions":"MCD适用于单峰、近对称/椭圆主群，不适合多峰。定标与MCD只用train；固定训练且cal/test独立可交换时，上尾split-conformal提供边际误报控制，不是条件保证或危险诊断。" + ("整批Holm在交换性下控制整批族系误报（FWER），不控制FDR。" if error_control==FAMILY_WISE else "单窗模式不控制整批族系错误率：同批多窗各自过线不等于整批保证。"),"protocol":"四特征、alpha与误报控制模式在运行前冻结；不以test选择特征、拟合、阈值或测试分位。筛选仅为人工独立补测线索。结果页与获批下载按完整测试集合一次性判定，筛选排序不重算p。"}
