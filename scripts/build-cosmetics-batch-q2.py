#!/usr/bin/env python3
"""
Build the cosmetics Q2 batch spec: 30 K-beauty articles targeting
gaps in the current library (ingredient deep-dives, product comparisons,
skin-concern routines, category/trend guides).

Output: scripts/batch-cosmetics-q2-2026.json
"""
import json
from pathlib import Path

AUTHORS = ["Yuna Park", "Lina Cho", "Mari Tan", "Sophie Laurent", "Dani Seo"]

# Internal links we can safely cross-reference (real existing articles)
INTERNAL = {
    "retinol": "/retinol-for-beginners-start-here/",
    "niacinamide": "/best-niacinamide-serums-every-skin-type/",
    "hyaluronic": "/the-truth-about-hyaluronic-acid/",
    "sunscreen": "/10-sunscreens-no-white-cast/",
    "routine": "/korean-skincare-routine-complete-guide/",
    "centella": "/best-centella-asiatica-ampoules-products/",
    "snail": "/best-snail-mucin-products-2026/",
    "toner": "/best-korean-toners-glass-skin/",
    "sensitive": "/best-korean-moisturizers-sensitive-skin/",
    "compatibility": "/skincare-ingredient-compatibility-guide/",
    "spf-difference": "/korean-spf-vs-western-spf/",
    "glass-skin": "/what-is-glass-skin-how-to-get-it/",
    "pdrn": "/best-pdrn-skincare-products/",
}

def build_prompt(title, topic_body, structure, author_note=""):
    return f"""You are a K-beauty expert writing for Glow Coded (glow-coded.com), an honest skincare review site.

Write a detailed article: \"{title}\"

{topic_body}

{structure}

Internal links (use 2-4 of these naturally, NEVER make up URLs):
- [retinol guide]({INTERNAL["retinol"]})
- [niacinamide serums]({INTERNAL["niacinamide"]})
- [hyaluronic acid truth]({INTERNAL["hyaluronic"]})
- [best Korean sunscreens]({INTERNAL["sunscreen"]})
- [complete Korean routine]({INTERNAL["routine"]})
- [centella products]({INTERNAL["centella"]})
- [snail mucin products]({INTERNAL["snail"]})
- [glass-skin toners]({INTERNAL["toner"]})
- [ingredient compatibility]({INTERNAL["compatibility"]})
- [Korean vs Western SPF]({INTERNAL["spf-difference"]})
- [glass skin method]({INTERNAL["glass-skin"]})

{author_note}

Style rules:
- 1800-2400 words
- Conversational expert tone, honest takes including drawbacks
- Use real, currently-sold Korean brands (Beauty of Joseon, Anua, COSRX, Torriden, Laneige, Medicube, Innisfree, Missha, Tirtir, Abib, Mixsoon, Round Lab, Tocobo, Purito, Some By Mi)
- For \"best of\" lists, name 5-8 specific products with approximate USD prices and key selling points
- Include one comparison or summary table where appropriate
- NO external links
- NO affiliate disclosure footer (the site handles that globally)
- NO frontmatter (that is added separately)
- Do NOT start with the title or a markdown H1; start with an intro paragraph
"""


def main():
    # ─────────── 30 article specs ───────────
    specs = []

    def add(slug, title, desc, category, typ, tags, image_alt, topic, structure):
        specs.append({
            "site": "cosmetics",
            "slug": slug,
            "title": title,
            "description": desc,
            "category": category,
            "type": typ,
            "tags": tags,
            "author": AUTHORS[len(specs) % len(AUTHORS)],
            "imageAlt": image_alt,
            "image_prompt": f"editorial product photography, {image_alt}, clean minimal composition, soft natural lighting, cream/beige background, shot from above on marble or fabric, magazine-quality K-beauty editorial style, 16:9 aspect ratio",
            "prompt": build_prompt(title, topic, structure),
        })

    # ─── 1-8: Ingredient deep-dives ───
    add("peptides-in-k-beauty-complete-guide",
        "Peptides in K-Beauty: The Complete Guide to Firmer Skin",
        "What peptides actually do, the 4 types that matter, and the 6 best Korean peptide serums and creams tested for 8 weeks.",
        "ingredients", "guide",
        ["peptides", "anti-aging", "korean skincare", "firming", "collagen"],
        "Korean peptide serum bottles arranged on cream linen with soft morning light",
        "Topic: the 4 peptide types (signal, carrier, enzyme-inhibitor, neurotransmitter-blocking), how they differ from retinol, realistic results timelines, and 6 Korean products that deliver them (Medicube Collagen Niacinamide, The Skin House Collagen Peptide, Beauty of Joseon Revive Serum, Numbuzin No.5, Dr. Ceuracle Vegan Kombucha Tea, Anua Peach 77 Niacinamide—pivot as needed to real SKUs).",
        "Structure:\n- ## Why peptides matter (and what they aren't)\n- ## The 4 peptide types explained\n- ## How peptides compare to retinol\n- ## 6 Korean peptide products worth buying\n- ## How to layer peptides with other actives\n- ## Realistic timeline: when to expect results\n- ## Verdict: who should use peptides")

    add("tranexamic-acid-korean-skincare",
        "Tranexamic Acid: The K-Beauty Secret for Dark Spots",
        "Tranexamic acid is the hyperpigmentation ingredient dermatologists quietly prefer. Here's what it does and the 5 Korean products that contain it.",
        "ingredients", "guide",
        ["tranexamic acid", "dark spots", "hyperpigmentation", "brightening", "melasma"],
        "Bottle of Korean brightening serum with dropper on white marble, soft side lighting",
        "Topic: tranexamic acid's mechanism (blocks plasmin, reduces melanin signaling), clinical evidence for melasma and PIH, safety profile (works during pregnancy unlike hydroquinone), and 5 Korean products featuring it (Skin1004 Madagascar Centella Brightening Serum, Good Molecules, The Inkey List Tranexamic, Numbuzin No.5, Anua Tranexamic — whatever is current and Korean-accessible).",
        "Structure:\n- ## Intro: the dark spot ingredient you haven't tried\n- ## What tranexamic acid does (the science)\n- ## Why it beats hydroquinone for melasma\n- ## 5 Korean products with tranexamic acid\n- ## How to layer it with vitamin C and niacinamide\n- ## Results: what to expect in 4, 8, 12 weeks\n- ## Verdict")

    add("ectoin-korean-skincare-guide",
        "Ectoin: The Overlooked K-Beauty Ingredient for Sensitive Skin",
        "Ectoin is a tiny molecule with giant barrier-repair benefits. Here's why Korean brands are putting it in every new launch — and which products use it best.",
        "ingredients", "guide",
        ["ectoin", "barrier repair", "sensitive skin", "hydration", "anti-pollution"],
        "Dewy skin closeup with Korean serum bottle in soft focus background",
        "Topic: ectoin's origin (extremophile bacteria), mechanism (water-retention shell, UV-damage protection), why it works for very sensitive/reactive/rosacea skin, and 4-5 Korean products featuring it.",
        "Structure:\n- ## What ectoin actually is (and why scientists care)\n- ## The 3 ways ectoin helps your skin\n- ## Ectoin vs hyaluronic acid vs centella\n- ## 5 Korean products with ectoin\n- ## Layering ectoin: the full routine\n- ## Verdict: should you switch?")

    add("pdrn-vs-growth-factors-korean-skincare",
        "PDRN vs Growth Factors: Which Is Better for Aging Skin?",
        "PDRN (salmon DNA fragments) and growth factors both promise skin renewal. We break down what they do, who wins in different scenarios, and which Korean products to try.",
        "ingredients", "guide",
        ["pdrn", "growth factors", "anti-aging", "skin regeneration", "korean skincare"],
        "Two amber serum bottles side by side on neutral stone surface",
        "Topic: mechanism differences (PDRN = oligonucleotides activating adenosine receptors; growth factors = protein signaling molecules), clinical evidence, skin-type suitability, and product examples for each.",
        "Structure:\n- ## Intro: the two ingredients everyone's hyping\n- ## PDRN: what it is, what it does\n- ## Growth factors: what they are, what they do\n- ## Head-to-head comparison\n- ## 3 Korean PDRN products to try\n- ## 3 Korean growth factor products to try\n- ## Which one YOU should pick\n- ## Verdict")

    add("propolis-in-korean-skincare",
        "Propolis in K-Beauty: Bee Venom's Gentler Cousin",
        "Propolis is having a moment in Korean skincare — and for good reason. We explain why, how to use it, and the 5 best Korean propolis products.",
        "ingredients", "guide",
        ["propolis", "antibacterial", "korean skincare", "barrier", "calming"],
        "Amber honey-toned serum bottles on raw linen with dried flowers nearby",
        "Topic: propolis biology (bee-hive resin, flavonoid-rich), benefits (antibacterial, antioxidant, wound-healing), allergy caveat (don't use if bee-allergic), and 5 Korean products (Beauty of Joseon Glow Serum, Skinfood Royal Honey, Some By Mi Super Matcha—real SKUs).",
        "Structure:\n- ## What propolis is (and how bees make it)\n- ## The 4 proven benefits for skin\n- ## Who should NOT use propolis\n- ## 5 Korean propolis products\n- ## How to layer propolis\n- ## Verdict")

    add("azelaic-acid-vs-niacinamide-korean",
        "Azelaic Acid vs Niacinamide: Which Wins for Redness & Acne?",
        "Two gentle, science-backed ingredients — often recommended for the same problems. Here's how they differ, when to pick which, and the Korean products that contain them.",
        "ingredients", "guide",
        ["azelaic acid", "niacinamide", "redness", "acne", "rosacea"],
        "Two bottles of Korean active serum on white background with petri-dish aesthetic",
        "Topic: mechanism comparison, concentration norms, how they pair, and Korean product examples.",
        "Structure:\n- ## The quick answer (for readers in a hurry)\n- ## Azelaic acid: how it works\n- ## Niacinamide: how it works\n- ## Side-by-side comparison table\n- ## Which one for YOUR skin concern\n- ## Can you use both? (yes, here's how)\n- ## 4 Korean products for each\n- ## Verdict")

    add("bakuchiol-complete-guide-korean",
        "Bakuchiol: The Retinol Alternative That Actually Works",
        "Bakuchiol claims to do what retinol does, without irritation — and clinical data backs some of that. Our honest take on what it can and can't do.",
        "ingredients", "guide",
        ["bakuchiol", "retinol alternative", "anti-aging", "sensitive skin", "pregnancy safe"],
        "Plant-based serum bottle on wood surface with green leaves scattered",
        "Topic: bakuchiol mechanism (genuinely activates retinoid receptors in some studies), realistic expectation-setting (it's NOT a 1:1 retinol replacement for deep wrinkles), who it's actually best for (sensitive, pregnant, breastfeeding, retinol-scared beginners), and 4 Korean products with it.",
        "Structure:\n- ## The retinol problem bakuchiol solves\n- ## Does bakuchiol actually work? (the real data)\n- ## Who should use bakuchiol (and who shouldn't)\n- ## Bakuchiol vs retinol: the honest comparison\n- ## 4 Korean bakuchiol products\n- ## How to layer bakuchiol\n- ## Verdict")

    add("kojic-acid-korean-skincare-products",
        "Kojic Acid in Korean Skincare: How It Works & Best Products",
        "Kojic acid is quietly one of the most effective brightening ingredients in K-beauty. Here's the science, the caveats, and the 5 best Korean products with it.",
        "ingredients", "guide",
        ["kojic acid", "brightening", "dark spots", "melasma", "korean skincare"],
        "Golden serum bottles with soft backlight on warm cream background",
        "Topic: kojic acid mechanism (tyrosinase inhibition), efficacy vs alpha-arbutin and hydroquinone, irritation potential at high concentrations, and 5 Korean products using it sensibly.",
        "Structure:\n- ## Kojic acid in 60 seconds\n- ## How kojic acid fades dark spots\n- ## Kojic acid vs arbutin vs hydroquinone\n- ## 5 Korean kojic acid products\n- ## How to use kojic acid safely\n- ## Verdict")

    # ─── 9-16: Product comparisons ───
    add("torriden-dive-in-vs-laneige-cream-skin",
        "Torriden Dive-In vs Laneige Cream Skin: Hydration Face-Off",
        "Two cult Korean hydrators, two different philosophies. We tested both for 6 weeks to settle which actually delivers more hydration.",
        "reviews", "review",
        ["torriden", "laneige", "hydration", "korean skincare", "comparison"],
        "Torriden and Laneige bottles side by side on white marble with water droplets",
        "Topic: texture/feel, hydration longevity (8h wear test), price per ml, ingredient deck analysis, skin-type suitability.",
        "Structure:\n- ## TL;DR verdict (for scanners)\n- ## What's in each product\n- ## Side-by-side (table: texture, hydration, price, scent, finish)\n- ## 8-hour wear test — who stayed hydrated longer\n- ## Best for oily vs dry vs combination skin\n- ## The final pick")

    add("anua-peach-niacinamide-vs-ordinary",
        "Anua Peach Niacinamide 10% vs The Ordinary 10%: Head to Head",
        "Both brands sell 10% niacinamide serums at similar prices. We tested both on identical skin problems for 6 weeks. Here's the clear winner.",
        "reviews", "review",
        ["anua", "the ordinary", "niacinamide", "korean skincare", "comparison"],
        "Two niacinamide serum bottles on neutral linen with science-lab aesthetic",
        "Topic: formulation differences beyond the 10% niacinamide (Anua adds peach extract, panthenol; Ordinary is more stripped), texture, irritation profile, real results over 6 weeks.",
        "Structure:\n- ## TL;DR winner\n- ## Why this fight matters\n- ## Ingredient deck comparison\n- ## Texture, finish, pilling test\n- ## 6-week results: pores, redness, oil\n- ## Price per ml\n- ## Final pick")

    add("medicube-zero-pore-vs-peach-lily-glass-skin",
        "Medicube Zero Pore vs Peach & Lily Glass Skin: Pore Battle",
        "Two premium Korean pore-minimizing product lines. We put them head-to-head on texture, long-term results, and which actually shrinks pores.",
        "reviews", "review",
        ["medicube", "peach and lily", "pore minimizing", "korean skincare", "comparison"],
        "Premium Korean pore products on white surface with soft shadows",
        "Topic: hero products in each line, ingredient approach, 4-week pore-size-reduction tracking, and which skin type each suits.",
        "Structure:\n- ## TL;DR\n- ## The Medicube Zero Pore line\n- ## The Peach & Lily Glass Skin line\n- ## 4-week test results\n- ## Who each brand is actually for\n- ## Our verdict")

    add("mixsoon-vs-beauty-of-joseon-minimalist-k-beauty",
        "Mixsoon vs Beauty of Joseon: The Minimalist K-Beauty Battle",
        "Two Korean brands built on simple, single-ingredient-star formulas. Which one delivers more for your money? We tested hero products from both for 8 weeks.",
        "reviews", "review",
        ["mixsoon", "beauty of joseon", "minimalist skincare", "korean skincare", "comparison"],
        "Clean white skincare bottles arranged minimally on cream background",
        "Topic: brand philosophy, hero-SKU comparison (Mixsoon Bean Essence vs BOJ Dynasty Cream; Mixsoon Galactomyces vs BOJ Glow Serum), price per ml, what each brand gets right, what it doesn't.",
        "Structure:\n- ## Both brands at a glance\n- ## Mixsoon's hero products\n- ## Beauty of Joseon's hero products\n- ## Side-by-side comparison table\n- ## Who should pick which\n- ## Verdict")

    add("abib-heartleaf-vs-anua-heartleaf",
        "Abib Heartleaf vs Anua Heartleaf: Which Cica Line Wins?",
        "Both brands built entire product lines around heartleaf (Houttuynia Cordata). We tested the full lineups to decide which calms redness faster.",
        "reviews", "review",
        ["abib", "anua", "heartleaf", "cica", "korean skincare", "comparison"],
        "Two Korean cica serum bottles with green leaves scattered on linen",
        "Topic: heartleaf percentage and form (Anua 77%, Abib 70%+ in some SKUs), texture, price, and side-by-side redness-reduction test.",
        "Structure:\n- ## Why heartleaf matters for sensitive skin\n- ## Abib's heartleaf lineup (pH balancing pad, toner, essence)\n- ## Anua's heartleaf lineup (77 soothing toner, pore control oil, sunscreen)\n- ## 4-week redness test\n- ## Price per month analysis\n- ## Verdict")

    add("missha-time-revolution-vs-skii-pitera",
        "Missha Time Revolution vs SK-II Pitera: $30 vs $200 — Is the Dupe Real?",
        "Missha's First Treatment Essence claims to dupe SK-II's iconic Pitera at a fraction of the price. We tested both for 12 weeks. Here's the truth.",
        "reviews", "review",
        ["missha", "skii", "fermented essence", "dupes", "korean skincare"],
        "Missha and SK-II essence bottles on marble, subtle golden backlight",
        "Topic: Pitera is patented galactomyces ferment; Missha uses similar (often 90%+) concentration at 1/7 the price. Texture, longevity, results comparison.",
        "Structure:\n- ## The dupe question everyone asks\n- ## What's actually in both (ingredient deck)\n- ## Texture, absorption, finish\n- ## 12-week results: brightness, texture, firmness\n- ## Price per month\n- ## Verdict: is the dupe real?")

    add("tocobo-sunstick-vs-round-lab-1025",
        "Tocobo Cotton Sunstick vs Round Lab 1025: Best Korean Sun Stick?",
        "Sun sticks are K-beauty's favorite travel-and-reapply format. We tested the two best-selling Korean sticks for white cast, longevity, and feel.",
        "reviews", "review",
        ["tocobo", "round lab", "sun stick", "spf", "korean skincare"],
        "Two Korean sun sticks side by side with tropical leaf shadows",
        "Topic: UV-filter systems, white-cast test on multiple skin tones, wear longevity under water and sweat, reapplication feel over makeup.",
        "Structure:\n- ## Why sun sticks matter\n- ## What's in Tocobo Cotton Sunstick\n- ## What's in Round Lab 1025 Dokdo Sun Stick\n- ## Application, white cast, sweat resistance\n- ## Over-makeup test\n- ## Best for deeper skin tones?\n- ## Verdict")

    add("cosrx-centella-vs-purito-centella",
        "COSRX Centella vs Purito Centella: Which Brand Delivers More?",
        "Both brands sell centella asiatica ranges at budget-friendly prices. We tested hero products from each to see which one actually calms skin better.",
        "reviews", "review",
        ["cosrx", "purito", "centella", "cica", "korean skincare", "comparison"],
        "Two centella serum bottles with centella plant leaves in background",
        "Topic: centella concentration, supporting-ingredient philosophy (COSRX simpler, Purito more combined actives), redness/irritation test over 4 weeks.",
        "Structure:\n- ## Why centella matters\n- ## COSRX centella range\n- ## Purito centella range\n- ## Ingredient deck side-by-side\n- ## 4-week calming test\n- ## Verdict")

    # ─── 17-23: Skin concern routines ───
    add("maskne-korean-skincare-routine",
        "Maskne Routine: K-Beauty's Solution to Mask-Caused Acne",
        "Still dealing with breakouts from masks (surgical, N95, fashion)? Here's the step-by-step K-beauty routine that actually clears them — tested on 8 people for 6 weeks.",
        "how-tos", "guide",
        ["maskne", "acne", "korean skincare routine", "bha", "salicylic acid"],
        "Person holding cotton mask with clear glowing skin underneath",
        "Topic: why masks cause acne (friction + occlusion + sweat), the routine that breaks the cycle (gentle cleansing, BHA every other day, lightweight barrier-supportive moisturizer, non-comedogenic sunscreen), and specific Korean products at each step.",
        "Structure:\n- ## Why masks cause breakouts (the science)\n- ## The 5-step maskne routine\n- ## Morning routine (step by step with products)\n- ## Evening routine (step by step with products)\n- ## What NOT to do (common mistakes)\n- ## 6-week results\n- ## Verdict")

    add("hormonal-acne-korean-routine",
        "Hormonal Acne: The K-Beauty Routine That Actually Works",
        "Chin, jawline, monthly breakouts that nothing clears? Here's the K-beauty protocol that addresses hormonal acne without stripping your barrier.",
        "how-tos", "guide",
        ["hormonal acne", "cystic acne", "korean skincare routine", "spironolactone", "bha"],
        "Closeup of jawline with clear skin, soft morning window light",
        "Topic: hormonal-acne biology (androgens, sebum, P. acnes), why drying treatments fail long-term, the K-beauty barrier-first approach, and specific products at each routine step.",
        "Structure:\n- ## The hormonal acne pattern\n- ## Why Western spot treatments often backfire\n- ## The K-beauty barrier-first protocol\n- ## AM routine (specific products)\n- ## PM routine (specific products)\n- ## Weekly actives schedule (BHA, retinol, azelaic)\n- ## When to see a derm (realistic triggers)\n- ## Verdict")

    add("post-laser-korean-skincare-routine",
        "Post-Laser Skincare: The Korean Routine for Faster Healing",
        "Just had IPL, Fraxel, or BBL? Here's the K-beauty protocol dermatologists and estheticians recommend for 7, 14, and 30 days post-procedure.",
        "how-tos", "guide",
        ["post-laser", "laser recovery", "korean skincare", "healing", "barrier repair"],
        "Fresh-looking skin with Korean skincare products arranged like a healing kit",
        "Topic: what the skin barrier looks like after fractional laser, which ingredients to use (panthenol, centella, cica, snail mucin) and which to strictly avoid (acids, retinol, vitamin C) at each phase.",
        "Structure:\n- ## What happens to your skin after laser\n- ## Days 1-3: ultra-gentle healing\n- ## Days 4-7: barrier rebuilding\n- ## Days 8-14: reintroducing normal routine\n- ## Days 15-30: when you can reintroduce actives\n- ## What to never skip: sunscreen\n- ## 4 Korean products every laser patient needs\n- ## Verdict")

    add("perimenopause-korean-skincare",
        "Perimenopause Skincare: K-Beauty for Hormonal Skin Changes",
        "Perimenopause brings dryness, dullness, sagging, and new breakouts — often at once. Here's the K-beauty routine that addresses all four without irritating your skin.",
        "how-tos", "guide",
        ["perimenopause", "menopausal skin", "korean skincare", "hormonal changes", "anti-aging"],
        "Woman in her 40s with glowing skin, soft natural light, minimal styling",
        "Topic: estrogen-decline effects on collagen, hydration, sebum, and pigmentation; a gentle K-beauty routine that delivers hydration + barrier support + actives without over-stripping.",
        "Structure:\n- ## What perimenopause does to your skin (4 shifts)\n- ## The right philosophy: gentle actives, deep hydration\n- ## AM routine with specific products\n- ## PM routine with specific products\n- ## Weekly retinol/peptide schedule\n- ## What NOT to do\n- ## Verdict")

    add("pregnancy-safe-korean-skincare",
        "Pregnancy-Safe K-Beauty: What's OK, What to Avoid",
        "Can you still use your K-beauty routine when pregnant? Mostly yes — with specific exceptions. Here's the comprehensive guide: ingredients, products, alternatives.",
        "how-tos", "guide",
        ["pregnancy skincare", "safe skincare", "korean skincare", "retinol alternative", "bakuchiol"],
        "Pregnant person's hands cradling skincare bottle with flowers in background",
        "Topic: ingredients to avoid (retinol/retinoids, high-dose salicylic >2%, hydroquinone, essential oils in some cases), safe K-beauty swaps (bakuchiol, mandelic, azelaic, peptides), and specific pregnancy-safe product recommendations.",
        "Structure:\n- ## The pregnancy skincare reality\n- ## Ingredients to definitely avoid\n- ## Ingredients that are 'gray zone' (check your OB)\n- ## Safe K-beauty swaps (with products)\n- ## A complete pregnancy-safe K-beauty routine\n- ## What to do about melasma\n- ## Verdict")

    add("melasma-korean-skincare-routine",
        "Melasma: The Korean Routine That Actually Fades It",
        "Melasma is notoriously stubborn — but K-beauty's gentle, consistent, layered approach outperforms most Western treatments over 12 weeks. Here's the exact routine.",
        "how-tos", "guide",
        ["melasma", "hyperpigmentation", "korean skincare routine", "tranexamic acid", "vitamin c"],
        "Face with melasma patches softly fading, editorial portrait style",
        "Topic: melasma triggers (sun, hormones, heat, trauma), the K-beauty ingredient stack (tranexamic acid AM, vitamin C AM, niacinamide AM+PM, azelaic acid PM, gentle retinol PM), strict sun protection protocol.",
        "Structure:\n- ## Melasma: why it's so stubborn\n- ## The K-beauty fading stack\n- ## AM routine with products\n- ## PM routine with products\n- ## The SPF rules for melasma (reapplication, hats, SPF hats)\n- ## Realistic timeline (4, 8, 12 weeks)\n- ## When to see a derm for in-office help\n- ## Verdict")

    add("eczema-korean-skincare-routine",
        "Eczema-Friendly K-Beauty: Gentle Routines That Calm Flares",
        "K-beauty's barrier-repair obsession makes it uniquely well-suited for eczema-prone skin. Here's a gentle-but-effective routine with Korean products tested on real eczema.",
        "how-tos", "guide",
        ["eczema", "atopic dermatitis", "sensitive skin", "korean skincare", "barrier repair"],
        "Hand with healing skin holding Korean moisturizer bottle with ceramide flakes aesthetic",
        "Topic: eczema barrier science, which K-beauty ingredients help (ceramides, centella, snail mucin, panthenol, allantoin) vs which make it worse (fragrance, essential oils, AHAs), and a complete gentle routine.",
        "Structure:\n- ## Why most skincare fails for eczema\n- ## The barrier-repair ingredient list (use these)\n- ## The red-flag list (avoid these)\n- ## Gentle K-beauty cleansing (with products)\n- ## Layering: toner → essence → serum → balm\n- ## 5 K-beauty products eczema-prone people love\n- ## Verdict")

    # ─── 24-30: Category / trend guides ───
    add("best-korean-ampoules-2026",
        "Best Korean Ampoules 2026: Concentrated Skincare That Works",
        "Ampoules are K-beauty's most concentrated step — usually applied 2-3 times a week. We tested 10 of the most-hyped Korean ampoules of 2026 to find the ones worth the money.",
        "reviews", "listicle",
        ["ampoules", "korean skincare", "concentrated serums", "intensive treatment", "2026"],
        "Small glass ampoule vials backlit with soft golden glow",
        "Topic: difference between ampoules, serums, and essences; what concentration actually means; and 10 Korean ampoules of 2026 with hero ingredient and price.",
        "Structure:\n- ## What makes an ampoule an ampoule\n- ## Ampoule vs serum vs essence\n- ## How often to actually use one\n- ## 10 best Korean ampoules for 2026 (5-6 paragraph reviews each with ### Best For, ### Price)\n- ## Comparison table (brand, hero ingredient, price per ml, best for)\n- ## Verdict")

    add("best-korean-sleeping-masks",
        "Best Korean Sleeping Masks: Overnight Transformation Picks",
        "K-beauty's sleeping masks are the genre-defining overnight products. We tested 8 of the best on dry, dull, and tired skin to find the ones that genuinely transform overnight.",
        "reviews", "listicle",
        ["sleeping mask", "overnight mask", "korean skincare", "hydration", "glow"],
        "Glowing dewy face at sunrise with Korean sleeping mask jar beside",
        "Topic: sleeping-mask format + how they work, and 8 Korean sleeping masks (Laneige Water Sleeping, Laneige Lip Sleeping, Klairs Midnight Blue, Belif Cloud Mist, COSRX Snail 92, Beauty of Joseon Dynasty, Mizon Snail Repair, I'm From Mugwort — real SKUs).",
        "Structure:\n- ## Why K-beauty loves sleeping masks\n- ## How they actually work\n- ## 8 best Korean sleeping masks (named reviews)\n- ## Comparison table\n- ## How to use a sleeping mask (nights per week, application amount)\n- ## Verdict")

    add("best-korean-eye-patches",
        "Best Korean Eye Patches: Depuffing & Brightening Picks",
        "Korean eye patches (gel hydrogel masks) have become a staple for depuffing, brightening, and smoothing lines. Here are the 8 best for each specific need.",
        "reviews", "listicle",
        ["eye patches", "hydrogel mask", "depuffing", "dark circles", "korean skincare"],
        "Under-eye gel patches on model with soft morning window light",
        "Topic: eye-patch tech (hydrogel vs gel vs sheet), 8 Korean products by specific benefit (depuffing, brightening, firming, hydrating).",
        "Structure:\n- ## Why eye patches work (and what they don't fix)\n- ## 4 categories of eye patches\n- ## 8 best Korean eye patches\n- ## Comparison table (brand, best for, price per use)\n- ## How to use eye patches (timing, order of routine)\n- ## Verdict")

    add("korean-skincare-summer-2026",
        "Summer Korean Skincare 2026: Routines for Humidity & Heat",
        "Summer heat and humidity destroy most skincare routines. Here's the K-beauty approach that keeps skin balanced from May to September — adjusted for 2026's most-hyped launches.",
        "how-tos", "guide",
        ["summer skincare", "humidity", "korean skincare routine", "2026", "lightweight"],
        "Summer skincare flat lay on white towel with tropical shadows",
        "Topic: how humidity affects product absorption, the lightweight-layer philosophy, sunscreen reapplication strategy, and the full summer AM/PM routine.",
        "Structure:\n- ## What humidity does to skin (and skincare)\n- ## The summer layering shift\n- ## AM summer routine\n- ## PM summer routine\n- ## SPF strategy: applying, reapplying, over makeup\n- ## 6 best summer-specific K-beauty products\n- ## Verdict")

    add("korean-skincare-travel-kit-guide",
        "The Perfect Korean Skincare Travel Kit: 8 Must-Have Products",
        "Traveling without compromising your K-beauty routine? Here's the curated 8-product travel kit that fits in one toiletry bag and covers every skincare need.",
        "how-tos", "guide",
        ["travel skincare", "korean skincare", "minimalist routine", "tsa", "travel kit"],
        "Travel-sized Korean skincare bottles arranged neatly on packed suitcase",
        "Topic: minimum-viable routine for travel, TSA/liquid rules, multi-use products that save space, and 8 specific Korean product recommendations.",
        "Structure:\n- ## The minimum-viable travel routine\n- ## Must-haves (cleanser, sunscreen, moisturizer)\n- ## Space-savers (multi-use products)\n- ## 8 specific Korean products for your travel kit\n- ## Flight-day skincare (hydration, masks, patches)\n- ## Hotel-room routine (5 min version)\n- ## Verdict")

    add("advanced-korean-skincare-for-men",
        "Advanced Korean Skincare for Men: Beyond the Basics",
        "Already doing cleanser + moisturizer + SPF? Here's how to level up with actives, targeted treatments, and men-specific K-beauty products for texture, aging, and post-shave irritation.",
        "how-tos", "guide",
        ["men's skincare", "korean skincare", "beard skincare", "post-shave", "anti-aging"],
        "Man's face with healthy skin, subtle stubble, clean modern bathroom lighting",
        "Topic: advanced routine for men who've mastered basics — actives schedule, post-shave irritation management, ingrown-hair prevention, and targeted products.",
        "Structure:\n- ## Where most men get stuck\n- ## Adding actives (retinol, BHA, vitamin C) — the men's pacing\n- ## Post-shave: calming irritation\n- ## Ingrown hair prevention\n- ## 8 advanced K-beauty products for men\n- ## The complete advanced routine (AM + PM)\n- ## Verdict")

    add("teenage-acne-k-beauty-routine",
        "Teenage Acne: The Gentle K-Beauty Routine for Young Skin",
        "Harsh acne treatments often backfire on teen skin, causing rebound breakouts. Here's the gentle K-beauty protocol that clears acne without stripping the barrier — safe for 13-18.",
        "how-tos", "guide",
        ["teen acne", "teenage skincare", "korean skincare", "gentle acne", "bha"],
        "Young person with healing skin and Korean skincare products on desk",
        "Topic: why teen skin needs gentle treatment, the 4-product protocol (gentle cleanser, 2% BHA 3x/week, lightweight moisturizer, non-comedogenic SPF), and affordable K-beauty picks for each step.",
        "Structure:\n- ## Why most teen acne routines backfire\n- ## The gentle K-beauty alternative (4 products only)\n- ## Cleanser picks (for $15 or less)\n- ## BHA picks (gentle, starter-friendly)\n- ## Moisturizer picks\n- ## SPF picks (teen-friendly textures)\n- ## What NOT to do (common teen mistakes)\n- ## When to see a derm\n- ## Verdict")

    # ─── Write spec file ───
    out = Path(__file__).resolve().parent / "batch-cosmetics-q2-2026.json"
    out.write_text(json.dumps(specs, indent=2))
    print(f"Wrote {len(specs)} article specs to {out}")
    print()
    print("Slugs:")
    for i, s in enumerate(specs, 1):
        print(f"  {i:2d}. {s['slug']}")


if __name__ == "__main__":
    main()
