@echo off
python -c "from pathlib import Path; p = Path.home() / 'Desktop' / 'gh_token.txt'; exists = p.exists(); b = p.read_bytes() if exists else None; print('exists:', 'yes' if exists else 'no'); print('size:', (str(len(b)) + ' bytes') if b is not None else 'n/a'); print('bom:', ('yes' if b.startswith(b'\xef\xbb\xbf') else 'no') if b is not None else 'n/a'); print('trailing_newline:', ('yes' if b.endswith((b'\n', b'\r')) else 'no') if b is not None else 'n/a'); print('cleanup:', 'Revoke the token in GitHub settings, securely delete gh_token.txt, and clear shell history.' if exists else 'No file to delete; revoke any previously exposed token and clear shell history.')"
if errorlevel 1 exit /b 1
exit /b 0
