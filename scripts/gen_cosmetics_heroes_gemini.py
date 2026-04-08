#!/usr/bin/env python3
"""Regenerate cosmetics hero images using Gemini 2.5 Flash Image."""

import os, sys, io, time
from PIL import Image
from google import genai
from google.genai import types

API_KEY = os.environ.get("GEMINI_API_KEY", "")
client = genai.Client(api_key=API_KEY)
MODEL = "gemini-2.5-flash-image"

OUT_DIR = "/Users/kapi7/satellite-websites/cosmetics/public/images"

HEROES = [
    ("ceramide-creams-barrier.jpg",
     "Create a beautiful flat-lay blog hero image in landscape orientation (wider than tall, 16:9 ratio). "
     "Arrange several Korean skincare ceramide cream jars and tubes aesthetically on a soft pink marble surface "
     "with dewy water droplets scattered around. Soft natural morning light from the left. "
     "Add a few small green eucalyptus leaves as accents. "
     "The products should have clean minimalist packaging with NO readable text or brand names visible. "
     "Premium beauty blog photography style. No text overlays. No watermarks."),

    ("korean-lip-products.jpg",
     "Create a beautiful flat-lay blog hero image in landscape orientation (16:9 ratio). "
     "Arrange Korean lip balms, lip masks, and lip tints on a pastel pink surface with fresh rose petals scattered around. "
     "Include a small lip-shaped sleeping mask pot. Glossy, hydrated, feminine aesthetic. "
     "Products should have clean simple packaging with NO readable text or brand names. "
     "Soft studio lighting. Premium beauty photography. No text overlays."),

    ("pdrn-skincare-products.jpg",
     "Create a minimalist flat-lay blog hero image in landscape orientation (16:9 ratio). "
     "Arrange Korean PDRN skincare serums and ampoules on white marble with a few salmon roe capsules as accents. "
     "Include a frosted glass dropper bottle and small amber ampoules. Clinical yet luxurious aesthetic. "
     "Products should have clean packaging with NO readable text or brand names. "
     "Soft diffused lighting. Premium beauty photography. No text overlays."),

    ("sheet-masks-by-concern.jpg",
     "Create a colorful flat-lay blog hero image in landscape orientation (16:9 ratio). "
     "Fan out 5 Korean sheet mask packets in different colors (pink, yellow, green, blue, white) on a clean white surface. "
     "Add fresh cucumber slices and small white flowers as accents. Spa day aesthetic. "
     "The mask packets should have clean colorful packaging with NO readable text or brand names. "
     "Bright natural lighting. Beauty flat lay photography. No text overlays."),

    ("dark-spots-hyperpigmentation.jpg",
     "Create a bright flat-lay blog hero image in landscape orientation (16:9 ratio). "
     "Arrange Korean brightening skincare products (serum bottles, essence, cream) on a light surface "
     "with lemon slices and a few vitamin C capsules as accents. Radiant glow aesthetic. "
     "Products should have clean frosted glass packaging with NO readable text or brand names. "
     "Warm soft lighting. Premium beauty photography. No text overlays."),

    ("korean-skincare-men.jpg",
     "Create a masculine flat-lay blog hero image in landscape orientation (16:9 ratio). "
     "Arrange sleek Korean men's skincare products (dark-colored bottles and tubes) on a dark slate or concrete surface "
     "with a eucalyptus sprig as accent. Minimalist grooming aesthetic. "
     "Products should have clean matte black packaging with NO readable text or brand names. "
     "Moody studio lighting. Men's product photography. No text overlays."),

    ("cushion-foundations-guide.jpg",
     "Create an elegant blog hero image in landscape orientation (16:9 ratio). "
     "Show two Korean cushion foundation compacts opened, revealing the cushion pad and mirror inside. "
     "Place them on a vanity surface with a soft makeup brush nearby. Dewy glass skin finish aesthetic. "
     "Products should have elegant gold-toned packaging with NO readable text or brand names. "
     "Soft warm lighting. Beauty photography. No text overlays."),

    ("cica-products-sensitive-skin.jpg",
     "Create a soothing flat-lay blog hero image in landscape orientation (16:9 ratio). "
     "Arrange Korean cica skincare products (cream, toner, serum, balm) on a mint green surface "
     "with fresh centella asiatica (gotu kola) leaves scattered around. Calming natural aesthetic. "
     "Products should have clean green-and-white packaging with NO readable text or brand names. "
     "Soft diffused lighting. Clean beauty photography. No text overlays."),

    ("cleansing-balms-oils.jpg",
     "Create a luxurious flat-lay blog hero image in landscape orientation (16:9 ratio). "
     "Arrange Korean cleansing balms and oil cleansers with cotton pads and gentle water splashes on a clean surface. "
     "Include a pump bottle and a jar of cleansing balm. Fresh double cleanse aesthetic. "
     "Products should have clean elegant packaging with NO readable text or brand names. "
     "Soft natural lighting. Beauty photography. No text overlays."),

    ("korean-toners-glass-skin.jpg",
     "Create a crystal-clear blog hero image in landscape orientation (16:9 ratio). "
     "Arrange several Korean toner bottles (clear and frosted glass) with water droplets and a glass prism "
     "on a reflective surface. Glass skin dewy aesthetic with light refractions. "
     "Products should have clean minimalist clear packaging with NO readable text or brand names. "
     "Bright studio lighting with prismatic light effects. Beauty photography. No text overlays."),

    ("moisturizers-under-25.jpg",
     "Create a cheerful flat-lay blog hero image in landscape orientation (16:9 ratio). "
     "Arrange affordable Korean moisturizer jars in pastel colors (mint, pink, lavender, peach) "
     "on a colorful pastel split-tone background. Budget-friendly beauty aesthetic. "
     "Products should have clean cute packaging with NO readable text, brand names, or price tags. "
     "Bright natural lighting. Product photography. No text overlays."),

    ("medicube-age-r-devices.jpg",
     "Create a sleek blog hero image in landscape orientation (16:9 ratio). "
     "Show Korean beauty tech devices — an LED face mask and a microcurrent roller device — "
     "on a futuristic white surface with soft blue LED glow accents. High-tech skincare aesthetic. "
     "Devices should be clean white with NO readable text or brand names. "
     "Studio lighting with subtle blue ambient glow. Technology product photography. No text overlays."),

    ("korean-body-care.jpg",
     "Create a luxurious flat-lay blog hero image in landscape orientation (16:9 ratio). "
     "Arrange Korean body lotions, body scrubs, and body oils with fluffy white towels on a spa-like marble surface. "
     "Body care pampering aesthetic with warm tones. "
     "Products should have clean elegant packaging with NO readable text or brand names. "
     "Warm soft lighting. Beauty lifestyle photography. No text overlays."),

    ("korean-hair-care-repair.jpg",
     "Create a beautiful blog hero image in landscape orientation (16:9 ratio). "
     "Arrange Korean hair care products (treatment oil, hair mask jar, repair serum) alongside flowing silky brown hair strands "
     "on a clean neutral surface. Healthy shiny hair aesthetic. "
     "Products should have clean amber-and-cream packaging with NO readable text or brand names. "
     "Soft studio lighting. Beauty photography. No text overlays."),

    ("anti-aging-serums.jpg",
     "Create an elegant blog hero image in landscape orientation (16:9 ratio). "
     "Arrange Korean anti-aging serums and ampoules (glass dropper bottles in amber and clear) "
     "with golden serum droplets on a luxurious surface with subtle gold accents. Premium skincare aesthetic. "
     "Products should have elegant glass packaging with NO readable text or brand names. "
     "Soft warm lighting. Luxury beauty photography. No text overlays."),
]

success = 0
for filename, prompt in HEROES:
    output = os.path.join(OUT_DIR, filename)
    print(f"Generating: {filename}...")
    
    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
            ),
        )
        
        saved = False
        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                img = Image.open(io.BytesIO(part.inline_data.data))
                img = img.convert("RGB")
                
                # Crop to 16:9 and resize to 1200x675
                target_ratio = 16 / 9
                current_ratio = img.width / img.height
                if current_ratio > target_ratio:
                    new_w = int(img.height * target_ratio)
                    left = (img.width - new_w) // 2
                    img = img.crop((left, 0, left + new_w, img.height))
                elif current_ratio < target_ratio:
                    new_h = int(img.width / target_ratio)
                    top = (img.height - new_h) // 2
                    img = img.crop((0, top, img.width, top + new_h))
                img = img.resize((1200, 675), Image.LANCZOS)
                
                img.save(output, "JPEG", quality=90)
                print(f"  OK: {filename} (1200x675)")
                saved = True
                success += 1
                break
        
        if not saved:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'text') and part.text:
                    print(f"  No image, text: {part.text[:100]}")
        
        time.sleep(4)  # Rate limit
        
    except Exception as e:
        print(f"  ERROR: {str(e)[:200]}")
        time.sleep(10)

print(f"\nDone: {success}/15 images generated")
