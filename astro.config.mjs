import { defineConfig } from 'astro/config';
import vue from '@astrojs/vue';
import unocss from '@unocss/astro';
import { presetUno, presetAttributify, presetIcons } from 'unocss';

import cloudflare from "@astrojs/cloudflare";

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
            DEFAULT: '#F0F7FF',
            soft: '#E6F2FF',
            card: '#FFFFFF',
            darker: '#DCEBFF',
          },
          text: {
            DEFAULT: '#615D6C',
            soft: '#4A4658',
            muted: '#6F8AB7',
            faint: '#9BAECF',
          },
          border: {
            DEFAULT: '#89BBFE',
            soft: '#ACEDFF',
          },
          brand: {
            50: '#F0F7FF',
            100: '#E6F2FF',
            200: '#CAE5FF',
            300: '#ACEDFF',
            400: '#89BBFE',
            500: '#5D9FFF',
            600: '#4A8AE6',
            700: '#3A6FB8',
            800: '#2D5690',
            900: '#1F3D68',
          },
          accent: {
            50: '#F0FAFF',
            100: '#E0F5FF',
            200: '#C7EFFF',
            300: '#6BBBFF',
            400: '#5DAEFC',
            500: '#4A9EF0',
            600: '#3A87D4',
            700: '#2C6BA8',
            800: '#1F5080',
            900: '#143858',
          },
          gold: {
            400: '#FFD68A',
            500: '#FFC04E',
            600: '#E0A038',
          },
          cyanx: {
            400: '#89BBFE',
            500: '#5D9FFF',
            600: '#3A6FB8',
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

  output: "hybrid",
  adapter: cloudflare()
});