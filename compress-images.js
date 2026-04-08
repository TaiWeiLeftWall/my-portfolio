const sharp = require('sharp');
const path = require('path');
const fs = require('fs');

const TARGET_SIZE = 1.5 * 1024 * 1024; // 1.5MB target
const MAX_SIZE = 2 * 1024 * 1024; // 2MB max
const QUALITY_START = 90;
const QUALITY_MIN = 40;

async function compressImage(inputPath, outputPath) {
    const fileSize = fs.statSync(inputPath).size;

    if (fileSize < TARGET_SIZE) {
        console.log(`Skip (already small): ${path.basename(inputPath)}`);
        return;
    }

    let quality = QUALITY_START;
    let outputBuffer;

    do {
        outputBuffer = await sharp(inputPath)
            .jpeg({ quality })
            .toBuffer();

        quality -= 5;
    } while (outputBuffer.length > MAX_SIZE && quality >= QUALITY_MIN);

    if (outputBuffer.length > MAX_SIZE) {
        // If still too large at min quality, resize
        const metadata = await sharp(inputPath).metadata();
        let width = metadata.width;
        let height = metadata.height;

        do {
            width = Math.floor(width * 0.9);
            height = Math.floor(height * 0.9);

            outputBuffer = await sharp(inputPath)
                .resize(width, height)
                .jpeg({ quality: QUALITY_MIN })
                .toBuffer();
        } while (outputBuffer.length > MAX_SIZE && width > 400);
    }

    fs.writeFileSync(outputPath, outputBuffer);
    console.log(`Compressed: ${path.basename(inputPath)} (${(fileSize / 1024 / 1024).toFixed(1)}MB -> ${(outputBuffer.length / 1024 / 1024).toFixed(1)}MB)`);
}

async function processDirectory(inputDir, outputDir) {
    if (!fs.existsSync(outputDir)) {
        fs.mkdirSync(outputDir, { recursive: true });
    }

    const files = fs.readdirSync(inputDir);

    for (const file of files) {
        const inputPath = path.join(inputDir, file);
        const stat = fs.statSync(inputPath);

        if (stat.isDirectory()) {
            await processDirectory(inputPath, path.join(outputDir, file));
        } else if (/\.(jpg|jpeg|png)$/i.test(file)) {
            const outputPath = path.join(outputDir, file);
            await compressImage(inputPath, outputPath);
        }
    }
}

// Usage
const inputDir = './images';
const outputDir = './images-compressed';

processDirectory(inputDir, outputDir)
    .then(() => console.log('\nDone!'))
    .catch(console.error);
