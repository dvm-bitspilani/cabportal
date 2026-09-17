import { describe, expect, it } from 'vitest'
import { displayDateTime, isoToLocalInput, localInputToIso } from './time'
describe('India timezone helpers',()=>{it('converts UTC into India time',()=>{expect(isoToLocalInput('2026-01-01T00:00:00Z')).toBe('2026-01-01T05:30')});it('serializes India input as ISO UTC',()=>{expect(localInputToIso('2026-01-01T05:30')).toContain('2026-01-01T00:00:00')});it('formats for display',()=>{expect(displayDateTime('2026-01-01T00:00:00Z')).toContain('05:30 AM')})})
