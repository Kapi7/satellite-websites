from markdown_quality import strip_article_wrapper, unclosed_fence
from fix_translation_artifacts import fix_prompt_leak

article = '# Guide\n\n```\n| Product | Cost |\n| --- | --- |\n| A | 15 |\n```\n## Example\nNormal prose.\n'
assert fix_prompt_leak(article)[0] == article
ending = '# Instructions\n\n```python\nprint("done")\n```\n'
assert fix_prompt_leak(ending)[0] == ending
assert strip_article_wrapper(ending) == ending
wrapped = '```markdown\n# Guide\nParagraph\n```'
assert strip_article_wrapper(wrapped) == '# Guide\nParagraph'
assert not unclosed_fence(article)
assert unclosed_fence(article.replace('\n```\n## Example', '\n## Example'))
assert not unclosed_fence('````md\n```python\ncode\n```\n````')
assert unclosed_fence('~~~python\nunfinished')
print('Markdown quality: internal and terminal fences preserved; broken fences detected.')
