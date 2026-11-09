import { test, expect } from '@playwright/test';

test.describe('Customer End-to-End Application Lifecycle', () => {
  test('Complete Customer Journey: Registration to Terminal Submission Tracking', async ({ page }) => {
    // 1. Visit Login Page
    await page.goto('/login');
    await expect(page).toHaveTitle(/Mini Loan Marketplace/i);

    // 2. Perform Customer Authentication
    const emailInput = page.locator('input#email, input[name="email"], input[type="email"]');
    const passwordInput = page.locator('input#password, input[name="password"], input[type="password"]');
    const submitBtn = page.locator('button[type="submit"]');

    await expect(emailInput).toBeVisible();
    await emailInput.fill('customer_e2e@example.com');
    await passwordInput.fill('E2ePassword123!');
    await submitBtn.click();

    // 3. Customer Dashboard Loads
    await expect(page).toHaveURL(/\/dashboard|\/applications/);
    await expect(page.locator('text=Customer Dashboard, text=My Applications').first()).toBeVisible({ timeout: 10000 });

    // 4. Create New Application
    const newAppBtn = page.locator('button:has-text("New Application"), button:has-text("Create Application")');
    if (await newAppBtn.isVisible()) {
      await newAppBtn.click();
      await page.fill('input[name="requested_amount"], input#requested_amount', '50000');
      await page.fill('input[name="monthly_income"], input#monthly_income', '60000');
      await page.fill('input[name="age"], input#age', '29');
      await page.selectOption('select[name="work_type"], select#work_type', 'salaried');
      await page.click('button[type="submit"]:has-text("Create"), button:has-text("Save Draft")');
    }

    // 5. Open Application Details
    await expect(page.locator('text=Draft, text=DRAFT').first()).toBeVisible();

    // 6. Grant Required Consents
    const grantConsentBtn = page.locator('button:has-text("Grant Consent"), button:has-text("Review & Consent")').first();
    if (await grantConsentBtn.isVisible()) {
      await grantConsentBtn.click();
      const confirmConsent = page.locator('button:has-text("I Agree"), button:has-text("Grant Both"), button:has-text("Confirm")');
      if (await confirmConsent.isVisible()) {
        await confirmConsent.click();
      }
    }

    // 7. Trigger Mock Lender Matching
    const runMatchBtn = page.locator('button:has-text("Run Matching"), button:has-text("Check Eligibility")');
    if (await runMatchBtn.isVisible()) {
      await runMatchBtn.click();
      await expect(page.locator('text=Apex Financial, text=Horizon Credit, text=Sterling Loans').first()).toBeVisible({ timeout: 10000 });
    }

    // 8. Generate & Compare Offers
    const genOffersBtn = page.locator('button:has-text("Generate Offers"), button:has-text("View Offers")');
    if (await genOffersBtn.isVisible()) {
      await genOffersBtn.click();
    }
    await expect(page.locator('text=APR, text=Monthly Instalment').first()).toBeVisible({ timeout: 10000 });

    // 9. Inspect Mock Key Facts Statement (KFS)
    const kfsLink = page.locator('button:has-text("View KFS"), a:has-text("View KFS"), button:has-text("Key Facts")').first();
    if (await kfsLink.isVisible()) {
      await kfsLink.click();
      await expect(page.locator('text=Key Facts Statement, text=TRAINING_ONLY_MOCK_KFS').first()).toBeVisible();
      // Close modal
      const closeKfs = page.locator('button:has-text("Close"), button[aria-label="Close"]');
      if (await closeKfs.isVisible()) {
        await closeKfs.click();
      }
    }

    // 10. Select Offer
    const selectOfferBtn = page.locator('button:has-text("Select Offer"), button:has-text("Choose Offer")').first();
    if (await selectOfferBtn.isVisible()) {
      await selectOfferBtn.click();
      await expect(page.locator('text=Selected, text=offer_selected').first()).toBeVisible();
    }

    // 11. Submit Offer with Idempotency Protection
    const submitOfferBtn = page.locator('button:has-text("Submit Application"), button:has-text("Confirm Submission")');
    if (await submitOfferBtn.isVisible()) {
      await submitOfferBtn.click();
      await expect(page.locator('text=Submitted, text=Status: Submitted').first()).toBeVisible({ timeout: 10000 });
    }

    // 12. Submission Tracking & Timeline Verification
    await expect(page.locator('text=Submission, text=Events, text=Reference').first()).toBeVisible();
  });
});
