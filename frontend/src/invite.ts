/**
 * 邀请链接的拼装与解析。
 *
 * 房间码是给"当面念"用的，链接是给"微信里发"用的：
 * 同一个房间，两种发法，最后落到同一个地方。
 */

export const CODE_LEN = 6

/** 从任意输入里抠出房间码：手输的 6 位，或者一条完整的邀请链接。 */
export function extractRoomCode(raw: string): string {
  const text = raw.trim()
  if (!text) return ''

  // 链接可能被别的参数包着，也可能带着尾随空格/引号，所以只认 key=value 那一段。
  const fromUrl = text.match(/[?&](?:r|room|code|room_code)=([a-z0-9]{4,12})/i)
  if (fromUrl) return fromUrl[1].toUpperCase().slice(0, CODE_LEN)

  return text.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, CODE_LEN)
}

/** 当前页面地址加上 ?r=CODE。部署在哪个域名下，链接就是哪个域名。 */
export function inviteUrl(code: string): string {
  const url = new URL(window.location.href)
  url.search = ''
  url.hash = ''
  url.searchParams.set('r', code.toUpperCase())
  return url.toString()
}

/** 打开页面时地址栏里带的邀请码，没有就是 null。 */
export function inviteFromLocation(): string | null {
  const params = new URLSearchParams(window.location.search)
  const raw = params.get('r') ?? params.get('room')
  if (!raw) return null
  const code = extractRoomCode(raw)
  return code.length === CODE_LEN ? code : null
}

/**
 * 进房之后把 ?r= 从地址栏抹掉。
 * 不抹的话，刷新一次就会再触发一遍自动进房，点「离开」也会立刻被拉回去。
 */
export function clearInviteFromLocation(): void {
  const url = new URL(window.location.href)
  if (!url.searchParams.has('r') && !url.searchParams.has('room')) return

  url.searchParams.delete('r')
  url.searchParams.delete('room')
  const search = url.searchParams.toString()
  window.history.replaceState(
    null,
    '',
    `${url.pathname}${search ? `?${search}` : ''}${url.hash}`,
  )
}
