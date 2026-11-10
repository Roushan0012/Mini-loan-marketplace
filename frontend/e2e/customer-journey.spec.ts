import { test, expect } from '@playwright/test';
import { validateRoleCredentials } from './credentials';

test.describe('Customer End-to-End Application Lifecycle', () => {
  test('Complete Customer Lifecycle: Registration/Login to Terminal Submission Tracking', async ({ page }) => {
    // Validate credentials before browser execution
    const { email: CUSTOMER_EMAIL, password: CUSTOMER_PASSWORD } = validateRoleCredentials(
      'E2E_CUSTOMER_EMAIL',
      'E2E_CUSTOMER_PASSWORD',
      'customer'
    );
    // 1. Visit Login Page
    await page.goto('/login');
    await expect(page).toHaveTitle(/Mini Loan Marketplace/i);

    // 2. Perform Customer Authentication
    const emailInput = page.locator('#login-email');
    const passwordInput = page.locator('#login-password');
    const submitBtn = page.locator('button[type="submit"]:has-text("Sign In")');

    await expect(emailInput).toBeVisible();
    await emailInput.fill(CUSTOMER_EMAIL);
    await passwordInput.fill(CUSTOMER_PASSWORD);
    await submitBtn.click();

    // 3. Customer Dashboard Loads
    await expect(page).toHaveURL(/\/customer\/dashboard/);
    await expect(page.locator('h1:has-text("Welcome back")')).toBeVisible({ timeout: 10000 });

    // 4. Navigate to Create Application Page
    const newAppBtn = page.locator('button:has-text("New Application"), button:has-text("Start First Application")').first();
    await expect(newAppBtn).toBeVisible();
    await newAppBtn.click();

    await expect(page).toHaveURL(/\/customer\/applications\/new/);
    await expect(page.locator('h2:has-text("Start Your Loan Application")')).toBeVisible();

    // 5. Fill Draft Application Form
    await page.fill('#age', '28');
    await page.selectOption('#work_type', 'salaried');
    await page.fill('#monthly_income', '55000.00');
    await page.fill('#requested_amount', '150000.00');

    const createBtn = page.locator('button[type="submit"]:has-text("Create Application")');
    await expect(createBtn).toBeVisible();
    await createBtn.click();

    // 6. Application Details Page Loads in DRAFT Status
    await expect(page).toHaveURL(/\/customer\/applications\/\d+/);
    await expect(page.locator('h2:has-text("Application #")')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('span.badge:has-text("DRAFT")').first()).toBeVisible();

    // 7. Grant Consent 1 (eligibility_matching)
    const consentCheckbox1 = page.locator('#accept-consent-eligibility_matching');
    await expect(consentCheckbox1).toBeVisible();
    await consentCheckbox1.check();

    const grantBtn1 = page.locator('button:has-text("Grant Consent")').first();
    await expect(grantBtn1).toBeVisible();
    await grantBtn1.click();

    await expect(page.locator('text=Consent active').first()).toBeVisible({ timeout: 10000 });

    // 8. Grant Consent 2 (sharing_with_mock_lenders)
    const consentCheckbox2 = page.locator('#accept-consent-sharing_with_mock_lenders');
    await expect(consentCheckbox2).toBeVisible();
    await consentCheckbox2.check();

    const grantBtn2 = page.locator('button:has-text("Grant Consent")').first();
    await expect(grantBtn2).toBeVisible();
    await grantBtn2.click();

    await expect(page.locator('text=All required consents are actively granted.')).toBeVisible({ timeout: 10000 });

    // 9. Trigger Multi-Lender Matching
    const runMatchingBtn = page.locator('button:has-text("Run Lender Matching")');
    await expect(runMatchingBtn).toBeVisible();
    await expect(runMatchingBtn).toBeEnabled();
    await runMatchingBtn.click();

    // Verify matching execution results display
    await expect(page.locator('text=Latest Execution Results (Run #')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('text=Apex Financial').first()).toBeVisible();

    // 10. Generate Mock Loan Offers
    const generateOffersBtn = page.locator('button:has-text("Generate Mock Offers")');
    await expect(generateOffersBtn).toBeVisible();
    await expect(generateOffersBtn).toBeEnabled();
    await generateOffersBtn.click();

    // Verify generated offer cards display financial terms
    await expect(page.locator('text=Annual APR').first()).toBeVisible({ timeout: 10000 });
    await expect(page.locator('text=Monthly Installment').first()).toBeVisible();

    // 11. Inspect Standardized Mock Key Facts Statement (KFS)
    const viewKfsBtn = page.locator('button:has-text("View Mock KFS")').first();
    await expect(viewKfsBtn).toBeVisible();
    await viewKfsBtn.click();

    // Verify modal content
    const kfsDialog = page.locator('div[role="dialog"][aria-labelledby="mock-kfs-title"]');
    await expect(kfsDialog).toBeVisible({ timeout: 10000 });
    await expect(page.locator('h2#mock-kfs-title')).toBeVisible();
    await expect(page.locator('text=Simulated Training Disclosure')).toBeVisible();

    // Close KFS modal
    const closeKfsBtn = kfsDialog.locator('button:has-text("Close")').first();
    await expect(closeKfsBtn).toBeVisible();
    await closeKfsBtn.click();
    await expect(kfsDialog).not.toBeVisible();

    // 12. Select Single Mock Offer
    const selectOfferBtn = page.locator('button:has-text("Select Offer")').first();
    await expect(selectOfferBtn).toBeVisible();
    await selectOfferBtn.click();

    // Verify confirmation modal
    const selectionModal = page.locator('div[role="dialog"][aria-labelledby="confirm-selection-title"]');
    await expect(selectionModal).toBeVisible({ timeout: 10000 });
    await expect(page.locator('text=Confirm Loan Offer Selection')).toBeVisible();

    const confirmSelectBtn = selectionModal.locator('button:has-text("Confirm Selection")');
    await expect(confirmSelectBtn).toBeVisible();
    await confirmSelectBtn.click();
    await expect(selectionModal).not.toBeVisible();

    // Verify offer status is updated to SELECTED
    await expect(page.locator('span.badge:has-text("SELECTED")').first()).toBeVisible({ timeout: 10000 });

    // 13. Idempotent Offer Submission to Simulated Mock Lender
    const submitLenderBtn = page.locator('button:has-text("Submit to Mock Lender")');
    await expect(submitLenderBtn).toBeVisible();
    await submitLenderBtn.click();

    // 14. Verify Submission Status & Event Timeline
    await expect(page.locator('text=Target Mock Lender')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('span.badge:has-text("SUBMITTED (DISPATCHED)")').or(page.locator('span.badge:has-text("ACCEPTED (MOCK)")'))).toBeVisible();
    await expect(page.locator('h4:has-text("Simulated Lender Event Ledger")')).toBeVisible();
  });
});
