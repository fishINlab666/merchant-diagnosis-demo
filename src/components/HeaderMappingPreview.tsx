import type { HeaderMappingPreview as HeaderMappingPreviewModel } from '../lib/reportMapping'

const matchLabels = {
  exact: '精确匹配',
  alias: '规则别名 · 待确认',
  unmapped: '未映射',
}

export function HeaderMappingPreview({ preview }: { preview: HeaderMappingPreviewModel }) {
  return (
    <section className="mapping-preview" aria-labelledby="mapping-preview-title">
      <div className="mapping-heading">
        <div><h3 id="mapping-preview-title">表头映射预览</h3><p>先确认字段，再进入数据校验；字段映射不等于指标口径已确认。</p></div>
        <span className={preview.canGenerate ? 'mapping-ready' : 'mapping-blocked'}>{preview.canGenerate ? '可以确认' : '暂不能生成'}</span>
      </div>

      {(preview.missingRequired.length > 0 || preview.duplicateStandards.length > 0) && <div className="mapping-missing" role="alert">
        {preview.missingRequired.length > 0 && <p>缺少必需字段：{preview.missingRequired.join('、')}</p>}
        {preview.duplicateStandards.length > 0 && <p>重复映射：{preview.duplicateStandards.join('、')}，请保留唯一权威列。</p>}
      </div>}

      <div className="mapping-modules" aria-label="可开放模块">
        {preview.modules.map((module) => (
          <div className={`mapping-module ${module.available ? 'available' : 'unavailable'}`} key={module.id}>
            <strong>{module.label}<span>{module.available ? '开放' : '关闭'}</span></strong>
            <small>{module.reason}</small>
          </div>
        ))}
      </div>

      <div className="table-scroll">
        <table className="mapping-table">
          <thead><tr><th>原字段</th><th>标准字段</th><th>匹配方式</th></tr></thead>
          <tbody>{preview.mappings.map((item, index) => (
            <tr key={`${item.source}-${index}`} className={item.match === 'unmapped' ? 'unmapped' : ''}>
              <td data-label="原字段">{item.source}</td>
              <td data-label="标准字段">{item.standard ?? '不纳入诊断'}</td>
              <td data-label="匹配方式">{matchLabels[item.match]}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </section>
  )
}
