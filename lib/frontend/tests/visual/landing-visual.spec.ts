import { test, expect } from '@playwright/test';

/**
 * Visual regression tests for the landing page
 *
 * These tests ensure pixel-perfect rendering during the refactoring
 * from shadow DOM to slot-based architecture.
 *
 * Run with:
 *   npm run test:visual                    # Run tests
 *   npm run test:visual:update            # Update baselines
 *   npm run test:visual:ui                # Interactive UI
 */

test.describe('Landing Page Visual Regression', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to landing page
    await page.goto('/');

    // Wait for all content to load
    await page.waitForLoadState('networkidle');

    // Wait for fonts to load (important for pixel-perfect comparison)
    await page.evaluate(() => document.fonts.ready);

    // Wait a bit more for any lazy-loaded images
    await page.waitForTimeout(1000);
  });

  test('hero section matches baseline', async ({ page }) => {
    const hero = page.locator('section.hero');
    await hero.scrollIntoViewIfNeeded();

    await expect(hero).toHaveScreenshot('hero-section.png', {
      maxDiffPixels: 100, // Allow minor anti-aliasing differences
      animations: 'disabled',
    });
  });

  test('news capsule matches baseline', async ({ page }) => {
    const newsCapsule = page.locator('news-capsule');
    if (await newsCapsule.isVisible()) {
      await expect(newsCapsule).toHaveScreenshot('news-capsule.png', {
        maxDiffPixels: 50,
        animations: 'disabled',
      });
    }
  });

  test('features carousel matches baseline', async ({ page }) => {
    const features = page.locator('section#features');
    await features.scrollIntoViewIfNeeded();

    await expect(features).toHaveScreenshot('features-section.png', {
      maxDiffPixels: 150,
      animations: 'disabled',
    });
  });

  test('MCP get started section matches baseline', async ({ page }) => {
    const getStarted = page.locator('section#get-started');
    await getStarted.scrollIntoViewIfNeeded();

    await expect(getStarted).toHaveScreenshot('get-started-section.png', {
      maxDiffPixels: 100,
      animations: 'disabled',
    });
  });

  test('tools section matches baseline', async ({ page }) => {
    const tools = page.locator('section.tools-section');
    await tools.scrollIntoViewIfNeeded();

    await expect(tools).toHaveScreenshot('tools-section.png', {
      maxDiffPixels: 100,
      animations: 'disabled',
    });
  });

  test('FAQ section matches baseline', async ({ page }) => {
    const faq = page.locator('section.faq-section');
    await faq.scrollIntoViewIfNeeded();

    await expect(faq).toHaveScreenshot('faq-section.png', {
      maxDiffPixels: 100,
      animations: 'disabled',
    });
  });

  test('final CTA section matches baseline', async ({ page }) => {
    const cta = page.locator('section.final-cta');
    await cta.scrollIntoViewIfNeeded();

    await expect(cta).toHaveScreenshot('final-cta-section.png', {
      maxDiffPixels: 100,
      animations: 'disabled',
    });
  });

  test('full page scroll matches baseline', async ({ page }) => {
    await expect(page).toHaveScreenshot('landing-full-page.png', {
      fullPage: true,
      maxDiffPixels: 1000, // Allow more tolerance for full page
      animations: 'disabled',
    });
  });
});

test.describe('Landing Page Visual Regression - Mobile', () => {
  test.beforeEach(async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(1000);
  });

  test('mobile hero section matches baseline', async ({ page }) => {
    const hero = page.locator('section.hero');
    await expect(hero).toHaveScreenshot('mobile-hero-section.png', {
      maxDiffPixels: 100,
      animations: 'disabled',
    });
  });

  test('mobile full page matches baseline', async ({ page }) => {
    await expect(page).toHaveScreenshot('landing-mobile-full-page.png', {
      fullPage: true,
      maxDiffPixels: 800,
      animations: 'disabled',
    });
  });
});

test.describe('Landing Page Visual Regression - Tablet', () => {
  test.beforeEach(async ({ page }) => {
    // Set tablet viewport
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(1000);
  });

  test('tablet full page matches baseline', async ({ page }) => {
    await expect(page).toHaveScreenshot('landing-tablet-full-page.png', {
      fullPage: true,
      maxDiffPixels: 900,
      animations: 'disabled',
    });
  });
});
