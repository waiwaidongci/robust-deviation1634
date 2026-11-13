import {useEffect,useState} from 'react';import {useNavigate} from 'react-router-dom';import {ArrowRight,LockKeyhole} from 'lucide-react';import {useResearchData} from '../hooks/useResearch';import {useAuth} from '../stores/auth';import {useAction} from '../hooks/useAction';import {StudySelector} from '../components/StudySelector';import {createRun} from '../api/runs';import {Notice} from '../components/common/Notice';import {ErrorControlModes} from '../constants/enums';import type {ErrorControl} from '../types/domain';
export function Configure(){
  const s=useResearchData(),{user}=useAuth(),a=useAction(),navigate=useNavigate(),
    [id,setId]=useState(0),[name,setName]=useState(''),[alpha,setAlpha]=useState(.05),[seed,setSeed]=useState(2026),
    [errorControl,setErrorControl]=useState<ErrorControl>('family_wise_holm');
  const study=s.studies.find(x=>x.id===id)||s.studies[0];
  useEffect(()=>{if(study)s.loadStudy(study.id)},[study?.id,s.loadStudy]);
  return <div className="page"><div className="page-title"><div><p className="eyebrow">TRAINING PROTOCOL / 03</p><h1>稳健拟合配置<span>不以测试分位，替代独立校准参照。</span></h1></div></div>
    <Notice message={s.error||a.error} onRetry={s.refresh}/>
    <div className="editor-grid"><form onSubmit={e=>{e.preventDefault();a.execute(async()=>{const r=await createRun({name,study_id:study.id,alpha,seed,error_control:errorControl});navigate('/results?run='+r.id)})}}>
      <label>研究名称<input aria-label="研究名称" value={name} onChange={e=>setName(e.target.value)} minLength={2} maxLength={120} required disabled={user?.role==='viewer'} placeholder="例如：主群四量独立补测研究"/></label>
      <StudySelector studies={s.studies} value={study?.id||0} onChange={setId}/>
      {study&&<div className={'source-note '+(!study.supported?'warning':'')}><b>{study.reason}</b><p>train{study.counts.train} / cal{study.counts.cal} / test{study.counts.test}</p></div>}
      <div className="form-heading"><span>01</span><h2>固定特征与支持比例</h2></div>
      <div className="feature-lock"><LockKeyhole size={17}/><div>{s.features.map(x=><span key={x.code}>{x.label} / {x.unit}</span>)}<small>按预定义次序全部四量，support_fraction=.8固定，只控制raw支持。</small></div></div>
      <div className="form-heading"><span>02</span><h2>误报控制（创建即冻结）</h2></div>
      <div className="control-lock" role="radiogroup" aria-label="误报控制模式">
        <label className={errorControl==='family_wise_holm'?'control-option active':'control-option'}>
          <input type="radio" name="error_control" value="family_wise_holm" checked={errorControl==='family_wise_holm'} onChange={()=>setErrorControl('family_wise_holm')}/>
          <span><b>整批族系 / Holm校正（推荐）</b><small>同批{study?study.counts.test:0}个测试窗一起判定：校正p=Holm(原始p)，按完整测试集合一次性控制整批族系误报；单窗过线不等于整批保证。</small></span>
        </label>
        <label className={errorControl==='single_window'?'control-option active':'control-option'}>
          <input type="radio" name="error_control" value="single_window" checked={errorControl==='single_window'} onChange={()=>setErrorControl('single_window')}/>
          <span><b>单窗边际 / 旧规则</b><small>逐窗p≤α即入选，不做整批校正；只提供单个新窗口的边际误报控制，不控制同批多窗的族系错误率。</small></span>
        </label>
      </div>
      <div className="form-heading"><span>03</span><h2>预设筛选与随机种子</h2></div>
      <div className="form-row"><label>预设alpha<select aria-label="预设alpha" value={alpha} onChange={e=>setAlpha(Number(e.target.value))}>{[.01,.025,.05,.1,.2].map(x=><option key={x} value={x}>{x}</option>)}</select></label>
        <label>拟合随机种子<input aria-label="随机种子" type="number" min="0" max="2147483647" value={seed} onChange={e=>setSeed(Number(e.target.value))}/></label></div>
      <p className="protocol">train内定标、FastMCD与重加权；cal固定评分参照；test只计算D²与p。上尾含等号，p分辨率1/(m+1)。<br/>alpha与误报控制模式在执行前冻结，不按test筛选数反复调参后再声称预设保证。结果页与下载均按完整测试集合判定，筛选排序不重算。</p>
      {user?.role!=='viewer'?<button className="primary" disabled={a.busy||!study?.supported}>提交稳健研究 <ArrowRight size={15}/></button>:<p className="role-note">阅读者可核对方案，提交需要研究员权限。</p>}
    </form>
    <aside className="method-note"><span className="eyebrow">MODEL BOUNDARY / 26</span><h2>稳健中心，<br/>仍有适用边界。</h2><ol>
      <li><b>单峰近对称主群</b><p>MCD不适合多峰群体。训练支持掩码只描述拟合，不当新样本标签。</p></li>
      <li><b>拒绝奇异拟合</b><p>训练常量、秩亏与奇异协方差失败，不用伪逆或补脊静默输出。</p></li>
      <li><b>误报控制分模式</b><p>单窗模式仅边际控制；整批Holm在交换性下控制整批族系误报（FWER），不是FDR、条件保证或危险诊断。</p></li>
    </ol></aside></div></div>;
}
