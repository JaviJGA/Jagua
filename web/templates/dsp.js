let taskId = new URLSearchParams(window.location.search).get('task_id');
let checkInterval;

function updateProgressBar(progress) {
    const fill = document.getElementById('progress-fill');
    const text = document.getElementById('progress-text');
    fill.style.width = progress + '%';
    text.textContent = progress + '% completado';
}

function updateTaskStatus(data) {
    // Actualizar barra de progreso
    updateProgressBar(data.progress);
    
    // Actualizar detalles
    document.getElementById('status-message').textContent = data.message || '';
    document.getElementById('urls-found').textContent = data.urls_found || '0';
    document.getElementById('urls-indexed').textContent = data.urls_indexed || '0';
    
    // Mostrar URL actual si existe
    const currentUrl = document.getElementById('current-url');
    if (data.current_url) {
        currentUrl.textContent = data.current_url;
        currentUrl.style.display = 'block';
    } else {
        currentUrl.style.display = 'none';
    }
    
    // Mostrar loader solo cuando está en progreso
    const loader = document.getElementById('loader');
    loader.style.display = data.status !== 'completed' ? 'block' : 'none';
    
    // Manejar estado completado
    if (data.status === 'completed') {
        clearInterval(checkInterval);
        document.getElementById('results-btn').style.display = 'block';
        
        // Redirigir automáticamente después de 3 segundos
        setTimeout(() => {
            window.location.href = `/search?q=${encodeURIComponent(data.query)}`;
        }, 3000);
    }
}

function checkStatus() {
    fetch(`/get_task_status?task_id=${taskId}`)
        .then(response => response.json())
        .then(data => {
            updateTaskStatus(data);
            
            // Continuar verificando si no está completado
            if (data.status !== 'completed') {
                setTimeout(checkStatus, 1000);
            }
        })
        .catch(error => {
            console.error('Error al verificar el estado:', error);
            setTimeout(checkStatus, 3000);
        });
}

// Iniciar la verificación cuando la página cargue
document.addEventListener('DOMContentLoaded', () => {
    // Obtener el ID de la tarea de la URL
    if (!taskId) {
        document.getElementById('status-message').textContent = 'Error: ID de tarea no especificado';
        return;
    }
    
    // Iniciar el chequeo periódico
    checkStatus();
});