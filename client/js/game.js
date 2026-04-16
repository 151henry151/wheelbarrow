// Main game entry point — placeholder
window.addEventListener('load', () => {
    const canvas = document.getElementById('game');
    canvas.width = 800;
    canvas.height = 600;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#4a7c3f';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = '#fff';
    ctx.font = '20px monospace';
    ctx.fillText('Wheelbarrow — coming soon', 280, 300);
});
