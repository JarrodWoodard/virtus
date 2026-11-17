import { messages } from '../i18n/runtime.js'
import type { PanelSection } from '../types.js'

export const setupRequiredTitle = (): string => messages().content.setup.title

export const buildSetupRequiredSections = (): PanelSection[] => [
  {
    text: 'Virtus needs a model provider before the TUI can start a session.'
  },
  {
    rows: [
      ['/model', 'configure provider + model in-place'],
      ['/setup', 'run full first-time setup wizard in-place'],
      ['Ctrl+C', 'exit and run `hermes setup` manually']
    ],
    title: 'Actions'
  }
]
