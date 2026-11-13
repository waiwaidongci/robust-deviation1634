import {Run} from '../types/domain';import {number} from '../utils/format';import {ErrorControlModes,isLegacyResult} from '../constants/enums';
export function RunSummary({run}:{run:Run}){
  const r=run.result,legacy=isLegacyResult(r);
  const modeLabel=legacy?'单窗边际 / 升级前旧档（v1原规则）':(r.error_control_label||ErrorControlModes[r.error_control||'single_window']);
  return <div className="run-summary"><div><span className="eyebrow">{r.study.code} / FIXED FOUR FEATURES</span><h3>{r.study.name}</h3><p>train {r.counts.train} / cal {r.counts.cal} / test {r.counts.test}</p></div>
    <div><span>冻结误报控制</span><b style={{fontSize:14}}>{modeLabel}</b><small>创建时冻结 · {legacy?'历史档案规则不变':'按完整测试集合判定'}</small></div>
    <div><span>预设α / 入选窗口</span><b>{number(r.alpha,3)}</b><small>{r.selected_count} / {r.counts.test}测试窗口{legacy?'（单窗p≤α）':r.error_control==='family_wise_holm'?'（Holm校正p≤α）':'（单窗p≤α）'}</small></div>
    <div><span>MCD训练支持</span><b>{r.fit.raw_support_count}<em> → {r.fit.support_count}</em></b><small>raw → reweighted / 仅train</small></div></div>;
}
