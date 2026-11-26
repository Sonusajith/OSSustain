import { describe, expect, it } from 'vitest'

import { parseRepositoryInput } from './githubRepositories'

describe('parseRepositoryInput', () => {
  it('recognizes a repository search term', () => {
    expect(parseRepositoryInput('react hooks')).toEqual({ kind: 'search', query: 'react hooks' })
  })

  it('recognizes owner/repository and strips a git suffix', () => {
    expect(parseRepositoryInput('  acme/widget.git  ')).toEqual({ kind: 'lookup', owner: 'acme', repository: 'widget' })
  })

  it('accepts a GitHub repository URL and rejects other hosts or extra path parts', () => {
    expect(parseRepositoryInput('https://github.com/acme/widget/')).toEqual({ kind: 'lookup', owner: 'acme', repository: 'widget' })
    expect(parseRepositoryInput('https://example.com/acme/widget').kind).toBe('invalid')
    expect(parseRepositoryInput('acme/widget/tree/main').kind).toBe('invalid')
  })

  it('asks for a usable search term when input is too short', () => {
    expect(parseRepositoryInput('a')).toEqual({ kind: 'invalid', message: 'Enter at least two characters to search GitHub.' })
  })
})
