/** Keep only <mark> tags from server-rendered snippets; strip everything else. */
export function sanitizeSnippet(snippet: string): string {
  return snippet.replace(/<\/?([a-zA-Z][a-zA-Z0-9]*)\b[^>]*>/g, (match, tag: string) => {
    if (String(tag).toLowerCase() !== 'mark') return ''
    return match.startsWith('</') ? '</mark>' : '<mark>'
  })
}
