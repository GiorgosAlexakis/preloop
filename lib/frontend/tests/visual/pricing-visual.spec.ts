import { test, expect } from '@playwright/test';

/**
 * Visual regression tests for the pricing page
 *
 * These tests ensure pixel-perfect rendering during the refactoring
 * from shadow DOM to slot-based architecture.
 */

test.describe('Pricing Page Visual Regression', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/pricing');
    await page.waitForLoadState('networkidle');
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(1000);
  });

  test('pricing hero section matches baseline', async ({ page }) => {
    const hero = page.locator('section.main-section').first();
    await expect(hero).toHaveScreenshot('pricing-hero.png', {
      maxDiffPixels: 100,
      animations: 'disabled',
    });
  });

  test('billing toggle matches baseline', async ({ page }) => {
    const toggle = page.locator('billing-toggle');
    await toggle.scrollIntoViewIfNeeded();

    await expect(toggle).toHaveScreenshot('billing-toggle.png', {
      maxDiffPixels: 50,
      animations: 'disabled',
    });
  });

  test('pricing cards (mobile view) match baseline', async ({ page }) => {
    const cards = page.locator('.plans-grid');
    if (await cards.isVisible()) {
      await cards.scrollIntoViewIfNeeded();

      await expect(cards).toHaveScreenshot('pricing-cards.png', {
        maxDiffPixels: 150,
        animations: 'disabled',
      });
    }
  });

  test('full pricing page matches baseline', async ({ page }) => {
    await expect(page).toHaveScreenshot('pricing-full-page.png', {
      fullPage: true,
      maxDiffPixels: 800,
      animations: 'disabled',
    });
  });
});

test.describe('Pricing Page Visual Regression - Desktop', () => {
  test.beforeEach(async ({ page }) => {
    // Desktop viewport where table is visible
    await page.setViewportSize({ width: 1200, height: 900 });
    await page.goto('/pricing');
    await page.waitForLoadState('networkidle');
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(1000);
  });

  test('pricing table matches baseline', async ({ page }) => {
    const table = page.locator('.pricing-table');
    if (await table.isVisible()) {
      await table.scrollIntoViewIfNeeded();

      await expect(table).toHaveScreenshot('pricing-table-desktop.png', {
        maxDiffPixels: 200,
        animations: 'disabled',
      });
    }
  });

  test('full pricing page desktop matches baseline', async ({ page }) => {
    await expect(page).toHaveScreenshot('pricing-full-page-desktop.png', {
      fullPage: true,
      maxDiffPixels: 800,
      animations: 'disabled',
    });
  });
});

test.describe('Pricing Page Visual Regression - Mobile', () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/pricing');
    await page.waitForLoadState('networkidle');
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(1000);
  });

  test('mobile pricing cards match baseline', async ({ page }) => {
    const cards = page.locator('.plans-grid');
    if (await cards.isVisible()) {
      await expect(cards).toHaveScreenshot('pricing-cards-mobile.png', {
        maxDiffPixels: 150,
        animations: 'disabled',
      });
    }
  });

  test('mobile full page matches baseline', async ({ page }) => {
    await expect(page).toHaveScreenshot('pricing-mobile-full-page.png', {
      fullPage: true,
      maxDiffPixels: 700,
      animations: 'disabled',
    });
  });
});

test.describe('Pricing Page Interactions', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/pricing');
    await page.waitForLoadState('networkidle');
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(1000);
  });

  test('annual billing toggle changes display', async ({ page }) => {
    const toggle = page.locator('billing-toggle');
    await toggle.scrollIntoViewIfNeeded();

    // Click to toggle to annual
    await toggle.locator('sl-button').last().click();
    await page.waitForTimeout(500);

    // Screenshot after toggle
    const cards = page.locator('.plans-grid');
    if (await cards.isVisible()) {
      await expect(cards).toHaveScreenshot('pricing-cards-annual.png', {
        maxDiffPixels: 150,
        animations: 'disabled',
      });
    }
  });
});
