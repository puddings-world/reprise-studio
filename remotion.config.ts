import { Config } from '@remotion/cli/config';
import path from 'node:path';

/**
 * Remotion bundles with webpack (not Vite), so it doesn't know the `@` /
 * `@data` path aliases declared in vite.config.ts + tsconfig. Mirror them
 * here so scene/token/timeline imports resolve identically in the render.
 */
Config.overrideWebpackConfig((config) => ({
  ...config,
  resolve: {
    ...config.resolve,
    alias: {
      ...(config.resolve?.alias ?? {}),
      '@': path.resolve(process.cwd(), 'src'),
      '@data': path.resolve(process.cwd(), 'data'),
    },
  },
}));

Config.setVideoImageFormat('jpeg');
