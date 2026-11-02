import { STANDARD_FIELDS, STANDARD_REQUIRED, type HeaderMappingPreview as HeaderMappingPreviewModel } from '../lib/reportMapping'

const matchLabels = {
  exact: '精确匹配',
  alias: '规则别名 · 待确认',
  unmapped: '未映射',
  manual: '手动校正',
}

interface HeaderMappingPreviewProps {
  preview: HeaderMappingPreviewModel
  sourceStoreId?: string
  profileStoreId?: string
  identityMismatch?: boolean
  onMappingChange?: (index: number, standard: string | null) => void
}

export function HeaderMappingPreview({ preview, sourceStoreId, profileStoreId, identityMismatch, onMappingChange }: HeaderMappingPreviewProps) {
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

      {sourceStoreId && <div className={`mapping-identity ${identityMismatch ? 'identity-error' : ''}`} role={identityMismatch ? 'alert' : 'status'}>
        <strong>门店身份确认</strong>
        <p>文件门店ID：{sourceStoreId}；档案门店ID：{profileStoreId || '未填写'}</p>
        {identityMismatch
          ? <p>档案与文件门店ID不一致，不能生成诊断。</p>
          : !profileStoreId
            ? <p>确认生成即认可该文件属于当前店铺，并在生成后绑定此 ID。</p>
            : <p>档案与文件门店ID一致。</p>}
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
              <td data-label="标准字段">
                <select aria-label={`${item.source}映射到标准字段`} disabled={!onMappingChange} value={item.standard ?? ''} onChange={(event) => onMappingChange?.(index, event.target.value || null)}>
                  <option value="">不纳入诊断</option>
                  <optgroup label="必需字段">{STANDARD_REQUIRED.map((field) => <option key={field} value={field}>{field}</option>)}</optgroup>
                  <optgroup label="可选字段">{STANDARD_FIELDS.filter((field) => !STANDARD_REQUIRED.includes(field as typeof STANDARD_REQUIRED[number])).map((field) => <option key={field} value={field}>{field}</option>)}</optgroup>
                </select>
              </td>
              <td data-label="匹配方式">{matchLabels[item.match]}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </section>
  )
}
