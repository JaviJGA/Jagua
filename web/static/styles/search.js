// Función para cambiar el tema - accesible globalmente
function setTheme(themeName) {
    const themeStyle = document.getElementById('theme-style');
    if (!themeStyle) return;  // Si no existe el elemento, salir
    
    let themePath = '';
    
    switch(themeName) {
        case 'light':
            themePath = "{{ url_for('static', filename='styles/search.css') }}";
            break;
        case 'dark':
            themePath = "{{ url_for('static', filename='styles/search-dark.css') }}";
            break;
        case 'blue':
            themePath = "{{ url_for('static', filename='styles/search-blue.css') }}";
            break;
        default:
            themePath = "{{ url_for('static', filename='styles/search.css') }}";
    }
    
    themeStyle.href = themePath;
    localStorage.setItem('selectedTheme', themeName);
}

// Configuración inicial al cargar la página
document.addEventListener('DOMContentLoaded', function() {
    // Configurar listeners para los botones de tema
    document.querySelectorAll('.theme-btn').forEach(button => {
        button.addEventListener('click', function() {
            const themeName = this.dataset.theme;
            setTheme(themeName);
        });
    });
    
    // Aplicar tema guardado (si existe)
    const savedTheme = localStorage.getItem('selectedTheme');
    if (savedTheme) {
        setTheme(savedTheme);
    } else {
        // Tema por defecto (opcional)
        setTheme('light');
    }
});