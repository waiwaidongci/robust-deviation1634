import {useState} from 'react';import {useSearchParams,Link} from 'react-router-dom';import {useResearchData} from '../hooks/useResearch';import {RunSummary} from '../components/RunSummary';import {DistancePlot} from '../components/DistancePlot';import {ScoreECDF} from '../components/ScoreECDF';import {CovarianceMatrix} from '../components/CovarianceMatrix';import {DataTable} from '../components/common/DataTable';import {StatusBadge} from '../components/common/StatusBadge';import {Notice} from '../components/common/Notice';import {number} from '../utils/format';import {isLegacyResult,ErrorControlModes} from '../constants/enums';
export function Results(){
  const s=useResearchData(true),[params]=useSearchParams(),[id,setId]=useState(Number(params.get('run'))||0),[selected,setSelected]=useState('');
  const run=id?s.runs.find(x=>x.id===id):s.runs[0],r=run?.result,
    item=r?.test?.find(x=>x.window.code===selected)||r?.test?.[0];
  // 旧档（v1）没有error_control/p_adj：按原单窗规则展示，校正p列回退为原始p
  const legacy=isLegacyResult(r),holm=!legacy&&r?.error_control==='family_wise_holm';
  return <div className="page results-page"><div className="page-title"><div><p className="eyebrow">ROBUST FIT & CALIBRATED TAIL / 04</p><h1>偏离与校准证据<span>测试窗口只有评分；中心与协方差来自训练。</span></h1></div><Link className="outline" to={'/notes'+(run?'?run='+run.id:'')}>记录人工补测 →</Link></div>
    <Notice message={s.error} onRetry={s.refresh}/>
    <div className="run-picker"><label>研究档案<select aria-label="研究档案" value={run?.id||''} onChange={e=>{setId(Number(e.target.value));setSelected('')}}>{s.runs.map(x=><option key={x.id} value={x.id}>#{x.id} / {x.name} / {x.status}</option>)}</select></label>{run&&<StatusBadge status={run.status}/>}</div>
    {run?.status==='completed'&&r&&item?<>
      <RunSummary run={run}/>
      {legacy&&<Notice message="该研究创建于误报控制升级前，按原单窗边际规则展示（p≤α即入选）；历史档案与获批下载格式保持不变。"/>}
      {r.selected_count===0&&r.no_selection_note&&<Notice message={r.no_selection_note}/>}
      <div className="result-grid"><section><DistancePlot result={r} selected={item.window.code} onSelect={setSelected}/>
        <div className="tail-reading"><label>测试窗口<select aria-label="测试窗口" value={item.window.code} onChange={e=>setSelected(e.target.value)}>{r.test.map(x=><option key={x.window.code} value={x.window.code}>{x.window.code} / D² {number(x.d2,3)} / p {number(x.p,4)}</option>)}</select></label>
          <dl><div><dt>联合D²</dt><dd>{number(item.d2,4)}</dd></div><div><dt>cal ≥ test</dt><dd>{item.cal_ge_count}<em> / {r.counts.cal}</em></dd></div><div><dt>原始上尾p</dt><dd>{number(item.p,4)}</dd></div>{!legacy&&<div><dt>Holm校正p</dt><dd>{number(item.p_adj,4)}</dd></div>}{!legacy&&holm&&<div><dt>Holm排名/乘子</dt><dd>第{item.holm_rank}名<em> ×{item.holm_multiplier}</em></dd></div>}</dl>
          <p className={item.selected?'warning':'supported'}>{item.selected?(holm?'校正p≤预设α：整批族系判定入选，探索补测线索，不是危险诊断。':'p≤预设α：探索补测线索，不是危险诊断。'):(holm?'校正p>预设α：整批族系判定未入选，不证明无偏离。':'p>预设α：未入本次探索筛选，不证明无偏离。')}</p>
          {item.selection_reason&&<p className="selection-reason">{item.selection_reason}</p>}
        </div></section>
      <aside><ScoreECDF result={r} selected={item}/><div className="reading-note"><h2>先读适用边界</h2><p>{r.assumptions}</p><p>{r.protocol}</p>{r.correction&&<p><b>校正规则：</b>{r.correction}</p>}<small>{r.tail}；分辨率{number(r.resolution,5)}。{r.resolution_note??''}</small></div></aside></div>
      {r.fit.warnings.length>0&&<Notice message={r.fit.warnings.join('；')}/>}
      <CovarianceMatrix result={r}/>
      <div className="section-heading"><h2>全部测试窗口明细</h2><span>{r.test.length}条 / 按完整测试集合一次性判定，筛选排序不重算 · {legacy?'单窗p≤α（旧档原规则）':holm?'Holm校正p≤α':'单窗p≤α'}</span></div>
      <div className="compact-table"><DataTable head={['窗口','D²','cal≥test','原始p',...(legacy?[]:['校正p','Holm排名','乘子']),'预设α','探索筛选','入选理由',...r.features.map(x=>x.label)]}>{r.test.map(x=><tr key={x.window.code} className={x.selected?'evidence-row':''} onClick={()=>setSelected(x.window.code)}><td>{x.window.code}</td><td>{number(x.d2,4)}</td><td>{x.cal_ge_count}</td><td>{number(x.p,4)}</td>{!legacy&&<><td>{number(x.p_adj,4)}</td><td>{holm?x.holm_rank:'—'}</td><td>{holm?x.holm_multiplier:'—'}</td></>}<td>{r.alpha}</td><td>{x.selected?'补测线索':'—'}</td><td className="reason-cell">{x.selection_reason??(legacy?'（升级前旧档：单窗p≤α判定，无校正字段）':'—')}</td>{r.features.map(f=><td key={f.code}>{number(x.window.values[f.code],3)}</td>)}</tr>)}</DataTable></div>
      <div className="section-heading"><h2>固定校准参照</h2><span>cal{r.counts.cal}条 / 完整分数，不以test替换</span></div>
      <div className="compact-table"><DataTable head={['窗口','角色','固定拟合D²']}>{r.calibration.map(x=><tr key={x.window.code}><td>{x.window.code}</td><td>cal</td><td>{number(x.d2,5)}</td></tr>)}</DataTable></div>
      <div className="section-heading"><h2>训练支持档案</h2><span>仅拟合成员 / 不作新窗口标签</span></div>
      <div className="compact-table"><DataTable head={['训练窗口','raw支持','重加权支持','训练D²']}>{r.input_snapshot.windows.filter(w=>w.split==='train').map((w,i)=><tr key={w.code}><td>{w.code}</td><td>{r.fit.raw_support_mask[i]?'是':'否'}</td><td>{r.fit.support_mask[i]?'是':'否'}</td><td>{number(r.fit.train_distances[i],5)}</td></tr>)}</DataTable></div>
      <p className="fingerprint">{r.algorithm_version} / 模式 {r.error_control??'single_window(legacy)'} / {ErrorControlModes[r.error_control??'single_window']}<br/>FIT SHA256 {r.fit_hash}<br/>INPUT SHA256 {r.input_hash}</p>
    </>:run?<div className="pending"><h2>{run.status==='failed'?'研究未完成':'独立worker正在训练与校准评分'}</h2><p>{run.error||'本页每2秒刷新，训练不读取cal/test。'}</p></div>:<p className="empty">正在读取研究快照；也可先从配置建立研究。</p>}</div>;
}
