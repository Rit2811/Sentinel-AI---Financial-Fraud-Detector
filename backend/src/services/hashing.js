import { createHash } from 'node:crypto'

function sortValue(value) {
  if (Array.isArray(value)) return value.map(sortValue)
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.keys(value)
        .sort()
        .map((key) => [key, sortValue(value[key])]),
    )
  }
  return value
}

export function canonicalize(value) {
  return JSON.stringify(sortValue(value))
}

export function sha256(value) {
  return createHash('sha256').update(value).digest('hex')
}
