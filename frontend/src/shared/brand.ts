import type { CSSProperties } from 'react'
import type { Branding } from './api/types.ts'

export function readableOn(hex: string) {
  const value = hex.replace('#', '')
  if (value.length !== 6) return '#fffdf9'
  const red = Number.parseInt(value.slice(0, 2), 16)
  const green = Number.parseInt(value.slice(2, 4), 16)
  const blue = Number.parseInt(value.slice(4, 6), 16)
  const luminance = (0.2126 * red + 0.7152 * green + 0.0722 * blue) / 255
  return luminance > 0.62 ? '#171717' : '#fffdf9'
}

export function brandVars(branding: Branding): CSSProperties {
  return {
    '--brand-primary': branding.primary_color,
    '--brand-on-primary': readableOn(branding.primary_color),
    '--brand-secondary': branding.secondary_color,
    '--brand-background': branding.background_color,
    '--brand-surface': branding.surface_color,
    '--brand-text': branding.text_color,
  } as CSSProperties
}

export const defaultBranding: Branding = {
  display_name: 'Zaylan',
  logo_url: '',
  primary_color: '#6B2E2E',
  secondary_color: '#B58A5A',
  background_color: '#F3E7D6',
  surface_color: '#FFFDF9',
  text_color: '#171717',
}
