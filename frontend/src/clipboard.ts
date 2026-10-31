/**
 * 复制文本。
 *
 * navigator.clipboard 只在 https / localhost 下可用，
 * 而朋友之间局域网用 http://192.168.x.x 打开是很常见的事，
 * 所以留一条 execCommand 的退路——丑，但能用。
 */
export async function copyText(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch {
    /* 没权限或被拒，走下面的兜底 */
  }

  try {
    const el = document.createElement('textarea')
    el.value = text
    el.setAttribute('readonly', '')
    el.style.position = 'fixed'
    el.style.top = '-1000px'
    el.style.opacity = '0'
    document.body.appendChild(el)
    el.select()
    el.setSelectionRange(0, text.length)
    const ok = document.execCommand('copy')
    document.body.removeChild(el)
    return ok
  } catch {
    return false
  }
}
