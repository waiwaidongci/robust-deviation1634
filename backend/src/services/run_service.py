import csv,io
from redis import Redis
from fastapi import HTTPException
from ..models import DeviationRun,ReviewNote
from ..models.deviation_run import SINGLE_WINDOW
from ..config.settings import REDIS_URL
from ..utils.serialize import record
from .study_service import get_study,create_snapshot
from .analysis_service import prepare_snapshot
from .audit_service import log
queue=Redis.from_url(REDIS_URL,decode_responses=True)
def list_runs(db):return [record(r) for r in db.query(DeviationRun).order_by(DeviationRun.id.desc())]
def get_run(db,rid):
    row=db.get(DeviationRun,rid)
    if not row:raise HTTPException(404,"偏离研究不存在")
    return row
def create_run(db,data,user):
    study=get_study(db,data.study_id);snapshot=create_snapshot(db,study)
    try:prepare_snapshot(snapshot)
    except ValueError as e:raise HTTPException(422,str(e))
    row=DeviationRun(**data.model_dump(),input_snapshot=snapshot,owner=user.name);db.add(row);db.flush();log(db,user.email,"deviation.enqueue",row.id);db.commit()
    try:queue.rpush('deviation:jobs',row.id)
    except Exception:row.status='failed';row.error='队列不可用，请重提';db.commit();raise HTTPException(503,row.error)
    return record(row)
def export_run(db,rid):
    row=get_run(db,rid)
    if row.status!='completed' or not db.query(ReviewNote).filter_by(run_id=rid,status='approved').first():raise HTTPException(403,'仅获批完成研究可导出')
    result=row.result or {}
    # 旧档回读：升级前v1结果没有error_control/p_adj字段，按原单窗规则导出且不改变既有列含义；
    # 升级后新建（含单窗模式）的运行一律导出含原始p/校正p/入选理由的完整新格式
    legacy=result.get('algorithm_version','').endswith('-v1') or 'error_control' not in result
    mode=result.get('error_control',SINGLE_WINDOW)
    o=io.StringIO();w=csv.writer(o);features=result.get('features',[])
    if legacy:
        w.writerow(['window','split',*[f['code'] for f in features],'D_squared','cal_ge_count','upper_tail_p','preset_alpha','selected','cal_m','seed','fit_hash','input_hash'])
        for x in result.get('test',[]):v=x['window'];w.writerow([v['code'],v['split'],*[v['values'][f['code']] for f in features],x['d2'],x['cal_ge_count'],x['p'],row.alpha,x['selected'],result['counts']['cal'],row.seed,result['fit_hash'],result['input_hash']])
        return o.getvalue()
    w.writerow(['window','split',*[f['code'] for f in features],'D_squared','cal_ge_count','upper_tail_p','holm_adjusted_p','holm_rank','holm_multiplier','error_control','preset_alpha','selected','selection_reason','cal_m','seed','fit_hash','input_hash'])
    for x in result['test']:
        v=x['window']
        w.writerow([v['code'],v['split'],*[v['values'][f['code']] for f in features],x['d2'],x['cal_ge_count'],x['p'],x['p_adj'],x['holm_rank'],x['holm_multiplier'],mode,row.alpha,x['selected'],x['selection_reason'],result['counts']['cal'],row.seed,result['fit_hash'],result['input_hash']])
    return o.getvalue()
