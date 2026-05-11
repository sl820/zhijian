with open('create_ppt.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find all lines with the issue - ASCII double quotes inside string literals
# Replace all instances of "text" inside desc/content strings with 「text」

fixed_lines = []
for i, line in enumerate(lines):
    # Check if this line has a desc: or content: with inner quotes
    # Simple heuristic: replace "..." that appear to be inside another string
    # by checking if the character before the quote is Chinese or the character after is Chinese

    result = []
    j = 0
    while j < len(line):
        c = line[j]
        if c == '"':
            # Check context - is this an inner quote?
            # Look at what comes before and after
            prev_char = line[j-1] if j > 0 else ''
            next_char = line[j+1] if j < len(line)-1 else ''

            # If prev is a Chinese character (CJK range), this is likely an inner quote
            prev_is_cjk = ord(prev_char) >= 0x4E00 and ord(prev_char) <= 0x9FFF if prev_char else False
            next_is_cjk = ord(next_char) >= 0x4E00 and ord(next_char) <= 0x9FFF if next_char else False

            if prev_is_cjk or next_is_cjk:
                # This is an inner Chinese quote, replace with corner bracket
                # Find the closing quote
                end = j + 1
                while end < len(line) and line[end] != '"':
                    end += 1
                inner = line[j+1:end]
                result.append('\u300c')  # 「
                result.append(inner)
                result.append('\u300d')  # 」
                j = end + 1
                continue
        result.append(c)
        j += 1

    fixed_lines.append(''.join(result))

with open('create_ppt.js', 'w', encoding='utf-8') as f:
    f.writelines(fixed_lines)

print('Done')
