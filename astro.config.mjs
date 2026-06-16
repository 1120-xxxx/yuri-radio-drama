import { defineConfig } from 'astro/config';
import vue from '@astrojs/vue';
import unocss from '@unocss/astro';
import { presetUno, presetAttributify, presetIcons } from 'unocss';

export default defineConfig({
  integrations: [
    vue(),
    unocss({
      presets: [
        presetUno(),
        presetAttributify(),
        presetIcons({
          scale: 1.2,
          warn: true,
        }),
      ],
      theme: {
        colors: {
          bg: {
            DEFAULT: '#16161f',
            soft: '#1a1a2e',
            card: '#1e1e2f',
            darker: '#0f0f17',
          },
          text: {
            DEFAULT: '#e5e7eb',
            soft: '#c8cad0',
            muted: '#9ca3af',
            faint: '#6b7280',
          },
          border: {
            DEFAULT: '#2d2d44',
            soft: '#232336',
          },
          brand: {
            50: '#fff1f5',
            100: '#ffe4ec',
            200: '#fecdd3',
            300: '#fda4af',
            400: '#fb7185',
            500: '#f472b6',
            600: '#e879a9',
            700: '#be185d',
            800: '#9d174d',
            900: '#831843',
          },
          accent: {
            50: '#eef2ff',
            100: '#e0e7ff',
            200: '#c7d2fe',
            300: '#a5b4fc',
            400: '#818cf8',
            500: '#6366f1',
            600: '#4f46e5',
            700: '#4338ca',
            800: '#3730a3',
            900: '#312e81',
          },
          gold: {
            400: '#fcd34d',
            500: '#fbbf24',
            600: '#f59e0b',
          },
          cyanx: {
            400: '#67e8f9',
            500: '#06b6d4',
            600: '#0891b2',
          },
        },
        fontFamily: {
          sans: 'system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", "PingFang SC", "Microsoft YaHei", sans-serif',
          mono: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
        },
      },
      shortcuts: {
        'btn': 'px-4 py-2 rounded-xl font-medium transition-all',
        'btn-primary': 'bg-gradient-to-r from-brand-500 to-accent-500 text-white hover:from-brand-400 hover:to-accent-400 shadow-lg shadow-brand-500/20',
        'btn-ghost': 'bg-bg-card text-text-soft hover:bg-bg-soft border border-border',
        'card': 'bg-bg-card rounded-2xl border border-border shadow-xl shadow-black/20 p-6 backdrop-blur',
        'card-glow': 'bg-bg-card rounded-2xl border border-border shadow-xl shadow-black/20 p-6 backdrop-blur hover:border-brand-500/40 hover:shadow-brand-500/10 transition-all',
        'chip': 'inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium',
      },
    }),
  ],
  site: 'https://example.com',
  build: {
    inlineStylesheets: 'auto',
  },
});
