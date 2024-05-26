import main

braille = "⠨⠁ ⠨⠇⠑⠕⠝ ⠨⠺⠑⠗⠞⠓⠒ ⠨⠏⠊⠙⠕ ⠏⠑⠗⠙⠮⠝ ⠁ ⠇⠕⠎ ⠝⠊⠋⠊⠕⠎ ⠏⠕⠗ ⠓⠁⠃⠑⠗ ⠙⠑⠙⠊⠉⠁⠙⠕ ⠑⠎⠞⠑ ⠇⠊⠃⠗⠕ ⠁ ⠥⠝⠁ ⠏⠑⠗⠎⠕⠝⠁ ⠍⠁⠽⠕⠗⠲ ⠨⠞⠑⠝⠛⠕ ⠥⠝⠁ ⠎⠑⠗⠊⠁ ⠑⠭⠉⠥⠎⠁⠒ ⠑⠎⠞⠁ ⠏⠑ ⠗⠎⠕⠝⠁ ⠍⠁⠽⠕⠗ ⠑⠎ ⠑⠇ ⠍⠑⠚⠕⠗ ⠁⠍⠊⠛⠕ ⠟⠥⠑ ⠞⠑⠝⠛⠕ ⠑⠝ ⠑⠇ ⠍⠥⠝⠙⠕⠲ ⠨⠞⠑⠝⠛⠕ ⠕⠞⠗⠁ ⠑⠭⠉⠥⠎⠁⠒ ⠑⠎⠞⠁ ⠏⠑⠗⠎⠕⠝⠁ ⠍⠁⠽⠕⠗ ⠑⠎ ⠉⠁⠏⠁⠵ ⠙⠑ ⠑⠝⠞⠑⠝⠙⠑⠗⠇⠕ ⠞⠕⠙⠕⠂ ⠓⠁⠎⠞⠁ ⠇⠕⠎ ⠇⠊⠃⠗⠕⠎ ⠏⠁⠗⠁ ⠝⠊⠋⠊⠕⠎⠲ ⠨⠞⠑⠝⠛⠕ ⠥⠝⠁ ⠞⠑⠗⠉⠑⠗⠁ ⠑⠭⠉⠥⠎⠁⠒ ⠑⠎⠞⠁ ⠏⠑⠗⠎⠕⠝⠁ ⠍⠁⠽⠕⠗ ⠧⠊⠧⠑ ⠑⠝ ⠨⠋⠗⠁⠝⠉⠊⠁⠂ ⠙⠕⠝⠙⠑ ⠏⠁⠎⠁ ⠓⠁⠍⠃⠗⠑ ⠽ ⠋⠗⠊⠕⠲ ⠨⠧⠑⠗⠙⠁⠙⠑⠗⠁⠍⠑⠝⠞⠑ ⠝⠑⠉⠑⠎⠊⠞⠁ ⠉⠕⠝⠎⠥⠑⠇⠕⠲ ⠨⠎⠊ ⠞⠕⠙⠁⠎ ⠑⠎⠁⠎ ⠑⠭⠉⠥⠎⠁⠎ ⠝⠕ ⠃⠁⠎⠞⠁⠎⠑⠝⠂ ⠃⠊⠑⠝ ⠏⠥⠑⠙⠕ ⠙⠑⠙⠊⠉⠁⠗ ⠑⠎⠞⠑ ⠇⠊⠃⠗⠕ ⠁⠇ ⠝⠊⠋⠊⠕ ⠟⠥⠑ ⠥⠝⠁ ⠧⠑⠵ ⠋⠥⠑ ⠑⠎⠞⠁ ⠏⠑⠗⠎⠕⠝⠁ ⠍⠁⠽⠕⠗⠲ ⠨⠞⠕⠙⠕⠎ ⠇⠕⠎ ⠍⠁⠽⠕⠗⠑⠎ ⠓⠁⠝ ⠎⠊⠙⠕ ⠏⠗⠊⠍⠑⠗⠕ ⠝⠊⠋⠊⠕⠎⠲ ⠶⠨⠏⠑⠗⠕ ⠏⠕⠉⠕⠎ ⠇⠕ ⠗⠑⠉⠥⠑⠗⠙⠁⠝⠶⠲ ⠨⠉⠕⠗⠗⠊⠚⠕⠂ ⠏⠥⠑⠎⠂ ⠍⠊ ⠙⠑⠙⠊⠉⠁⠞⠕⠗⠊⠁⠒"
texto = main.user_braille(braille)

print(texto)