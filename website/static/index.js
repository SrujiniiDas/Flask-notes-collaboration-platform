// Rich-text note editor
const editorElement = document.getElementById('editor-container');
if (editorElement) {
  const quill = new Quill('#editor-container', {
    theme: 'snow',
    placeholder: 'Start writing…',
    modules: {
      toolbar: [
        [{ header: [1, 2, 3, false] }],
        ['bold', 'italic', 'underline'],
        [{ list: 'ordered' }, { list: 'bullet' }],
        ['blockquote', 'link'],
        ['clean']
      ]
    }
  });
  const form = document.getElementById('note-form') || document.getElementById('edit-note-form');
  form?.addEventListener('submit', () => {
    const hidden = document.getElementById('note_content_hidden') || document.getElementById('note-content-hidden');
    if (hidden) hidden.value = quill.root.innerHTML;
  });
}

// Keep the selected filename visible in Bootstrap's custom input.
document.querySelectorAll('.custom-file-input').forEach(input => {
  input.addEventListener('change', () => {
    const label = input.nextElementSibling;
    if (label) label.textContent = input.files?.[0]?.name || 'Choose file';
  });
});

// Owner-only note deletion. Server validates ownership again.
window.deleteNote = function deleteNote(noteId) {
  if (!confirm('Delete this note permanently?')) return;
  window.apiFetch('/delete-note', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ noteId })
  })
    .then(async response => {
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.error || 'Failed to delete note');
      window.location.href = '/my-notes';
    })
    .catch(error => alert(error.message));
};
