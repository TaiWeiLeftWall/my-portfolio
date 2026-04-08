/**
 * R2 Image Upload Worker
 * Receives images and uploads to Cloudflare R2
 */

export default {
  async fetch(request, env, ctx) {
    if (request.method !== 'POST' || !request.url.endsWith('/upload')) {
      return new Response('Not Found', { status: 404 });
    }

    try {
      const formData = await request.formData();
      const file = formData.get('image');
      const category = formData.get('category') || 'uncategorized';
      const dateStr = formData.get('date') || new Date().toISOString().slice(0, 10);

      if (!file || !(file instanceof File)) {
        return Response.json({ error: 'No image provided' }, { status: 400 });
      }

      // Read image data
      const arrayBuffer = await file.arrayBuffer();
      const uint8Array = new Uint8Array(arrayBuffer);

      // Generate filename
      const ext = file.name.split('.').pop() || 'jpg';
      const filename = `${Date.now()}-${Math.random().toString(36).slice(2)}.${ext}`;
      const r2Path = `images/${category}/${dateStr}/${filename}`;

      // Upload to R2
      await env.MY_BUCKET.put(r2Path, uint8Array, {
        httpMetadata: {
          contentType: file.type || 'image/jpeg'
        }
      });

      // Return the R2 URL
      const r2Url = `https://pub-ba17e7db6d874ec89ad295b72ef1e9d8.r2.dev/${r2Path}`;

      return Response.json({
        success: true,
        filename,
        path: r2Path,
        url: r2Url
      });

    } catch (error) {
      console.error('Upload error:', error);
      return Response.json({ error: error.message }, { status: 500 });
    }
  }
};
