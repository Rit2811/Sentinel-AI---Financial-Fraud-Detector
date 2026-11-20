const { chromium } = require('C:/Users/siddh/AppData/Roaming/npm/node_modules/playwright')
const path = require('path')
const fs = require('fs')

async function renderPdf() {
  console.log('📄 Launching Playwright Chromium for PDF generation...')
  const browser = await chromium.launch({
    headless: true,
  })

  const context = await browser.newContext()
  const page = await context.newPage()

  const htmlPath = path.resolve('docs/presentation_guide.html')
  const pdfPath = path.resolve('docs/Sentinel_AI_Evaluator_Presentation_Guide.pdf')
  const desktopPdfPath = 'C:/Users/siddh/OneDrive/Desktop/Sentinel_AI_Evaluator_Presentation_Guide.pdf'

  console.log(`🌐 Loading HTML from: ${htmlPath}`)
  await page.goto(`file://${htmlPath}`, { waitUntil: 'networkidle' })

  console.log(`🖨️ Generating PDF: ${pdfPath}`)
  await page.pdf({
    path: pdfPath,
    format: 'A4',
    printBackground: true,
    margin: {
      top: '16mm',
      bottom: '16mm',
      left: '14mm',
      right: '14mm',
    },
  })

  try {
    fs.copyFileSync(pdfPath, desktopPdfPath)
    console.log(`📋 Copied directly to Desktop: ${desktopPdfPath}`)
  } catch (e) {
    console.log('Desktop copy note:', e.message)
  }

  await browser.close()
  console.log('✅ PDF generated successfully!')
}

renderPdf().catch((err) => {
  console.error('Error generating PDF:', err)
  process.exit(1)
})
