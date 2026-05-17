#!/bin/bash

# Ana ekrana shortcut ekle
echo "#!/bin/bash
termux-open-url 'termux://com.termux/com.termux.app.RunCommandService?command=cd%20~/music-analyzer%20%26%26%20python%20main.py'
" > ~/music-analyzer-shortcut

chmod +x ~/music-analyzer-shortcut
echo "Shortcut oluşturuldu: ~/music-analyzer-shortcut"