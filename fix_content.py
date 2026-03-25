#!/usr/bin/env python3
"""Remove AI-style em-dashes and polish content for human feel."""

import re
import glob

def fix_emdashes(text):
    # Replace " — " with more natural connectors
    replacements = [
        # Bold list items with dash descriptions
        (r'\*\*([^*]+)\*\*: ', r'**\1.** '),
        (r'\*\*([^*]+)\*\* — ', r'**\1.** '),
        # Parenthetical asides
        (r' — ([^—\n]{1,60}) — ', r' (\1) '),
        # Trailing dashes that act as continuation
        (r' — (which|that|where|when|because|since|though|but|and|or|so) ', r'. \1 '),
        # Remaining dashes to periods/semicolons contextually
    ]
    
    for pattern, repl in replacements:
        text = re.sub(pattern, repl, text)
    
    # Replace remaining " — " with ". " or ", " or " (and) "
    # Do it carefully line by line
    lines = text.split('\n')
    new_lines = []
    for line in lines:
        # Skip frontmatter
        if line.startswith('---') or line.startswith('title:') or line.startswith('description:'):
            new_lines.append(line)
            continue
        
        # In list items, replace dash with period
        if line.strip().startswith('- ') or line.strip().startswith('* '):
            line = line.replace(' — ', '. ')
        else:
            # In prose, alternate between period and comma based on context
            count = 0
            while ' — ' in line and count < 20:
                count += 1
                idx = line.index(' — ')
                before = line[:idx]
                after = line[idx+3:]
                
                # If after starts with lowercase, use comma or semicolon
                if after and after[0].islower():
                    line = before + '; ' + after
                else:
                    line = before + '. ' + after
        
        new_lines.append(line)
    
    return '\n'.join(new_lines)

def fix_descriptions(text):
    """Fix frontmatter descriptions that have em-dashes."""
    lines = text.split('\n')
    new_lines = []
    for line in lines:
        if line.startswith('description:'):
            line = line.replace(' — ', '. ')
            line = line.replace(' — ', '. ')
        new_lines.append(line)
    return '\n'.join(new_lines)

files = glob.glob('/Users/kapi7/satellite-websites/*/src/content/blog/*.mdx')

for fpath in sorted(files):
    with open(fpath, 'r') as f:
        original = f.read()
    
    text = fix_descriptions(original)
    text = fix_emdashes(text)
    
    if text != original:
        with open(fpath, 'w') as f:
            f.write(text)
        count = original.count(' — ') - text.count(' — ')
        remaining = text.count(' — ')
        print(f"  Fixed {fpath.split('/')[-1]}: removed {count} dashes, {remaining} remaining")
    else:
        print(f"  No changes: {fpath.split('/')[-1]}")

print("\nDone!")
