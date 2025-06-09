function setTheme(themeName) {
            const themeStyle = document.getElementById('theme-style');
            if (!themeStyle) {
                console.error('No se encontró el elemento theme-style');
                return;
            }
            
            const themeUrl = themeStyle.getAttribute(`data-${themeName}-url`);
            if (!themeUrl) {
                console.error(`No se encontró URL para el tema ${themeName}`);
                return;
            }
            
            themeStyle.href = themeUrl;
            localStorage.setItem('selectedTheme', themeName);
            console.log(`Tema cambiado a ${themeName}: ${themeUrl}`);
        }

        document.addEventListener('DOMContentLoaded', function() {
            // Configurar listeners para los botones
            document.querySelectorAll('.theme-btn').forEach(button => {
                button.addEventListener('click', function() {
                    const themeName = this.dataset.theme;
                    setTheme(themeName);
                });
            });
            
            // Aplicar tema guardado o el predeterminado
            const savedTheme = localStorage.getItem('selectedTheme') || 'light';
            setTheme(savedTheme);
        });