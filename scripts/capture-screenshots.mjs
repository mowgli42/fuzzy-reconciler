/**
 * Capture operational UI walkthrough images for docs/screenshots/
 */
import { chromium } from 'playwright'
import path from 'path'
import { fileURLToPath } from 'url'
import fs from 'fs'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.resolve(__dirname, '..')
const OUT = path.join(ROOT, 'docs', 'screenshots')
fs.mkdirSync(OUT, { recursive: true })

const BASE = process.env.DEMO_URL || 'http://127.0.0.1:5173'

async function shot(page, name) {
  const file = path.join(OUT, name)
  await page.screenshot({ path: file, fullPage: false })
  console.log('wrote', file)
}

async function main() {
  const browser = await chromium.launch({ headless: true })
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  await page.goto(BASE, { waitUntil: 'networkidle' })
  await page.waitForTimeout(400)
  await shot(page, '01-ingestion.png')

  await page.getByRole('button', { name: 'Load sample inventories' }).click()
  await page.waitForSelector('text=Matching thresholds')
  await page.waitForTimeout(300)
  await shot(page, '02-configuration.png')

  const loose = page.getByRole('button', { name: 'Facility Loose' })
  if (await loose.count()) await loose.click()

  await page.getByRole('button', { name: 'Run comparison' }).click()
  await page.waitForSelector('.kpis')
  await page.waitForTimeout(1000)
  await shot(page, '03-results-dashboard.png')

  const temporal = page.getByRole('button', { name: 'Temporal' }).first()
  if (await temporal.count()) await temporal.click()
  await page.locator('.table-wrap tbody tr').first().click()
  await page.waitForSelector('aside.panel')
  await page.waitForTimeout(400)
  await shot(page, '04-detail-temporal.png')

  if (await temporal.count()) await temporal.click()
  const spatial = page.getByRole('button', { name: 'Spatial' }).first()
  if (await spatial.count()) await spatial.click()
  await page.locator('.table-wrap tbody tr').first().click()
  await page.waitForTimeout(400)

  // Keep separate disposition + commit
  await page.getByRole('complementary').getByRole('button', { name: 'Keep separate' }).click()
  await page.getByRole('button', { name: 'Commit keep separate' }).click()
  await page.waitForTimeout(300)
  await shot(page, '05-detail-spatial.png')

  // Merge another pair
  await page.locator('.table-wrap tbody tr').nth(1).click()
  await page.getByRole('complementary').getByRole('button', { name: 'Merge', exact: true }).click()
  await page.getByRole('button', { name: 'Commit disposition' }).click()
  await page.waitForTimeout(300)

  await page.getByRole('button', { name: 'Proceed to Merge board' }).click()
  await page.waitForTimeout(400)
  await shot(page, '06-reconciled-master.png')

  await page.getByRole('button', { name: 'Publish working set' }).click()
  await page.waitForTimeout(300)
  await shot(page, '07-map-spatial-filter.png')

  await browser.close()
  console.log('Done')
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
