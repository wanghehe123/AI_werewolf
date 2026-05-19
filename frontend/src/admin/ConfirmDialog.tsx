interface ConfirmDialogProps {
  isOpen: boolean;
  title: string;
  message: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({ isOpen, title, message, onConfirm, onCancel }: ConfirmDialogProps) {
  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onCancel}>
      <div className="modal-panel modal-confirm" onClick={(e) => e.stopPropagation()}>
        <h3 className="modal-title">{title}</h3>
        <p className="confirm-message">{message}</p>
        <div className="admin-form-actions">
          <button className="danger-action" type="button" onClick={onConfirm}>
            确认
          </button>
          <button className="ghost-action" type="button" onClick={onCancel}>
            取消
          </button>
        </div>
      </div>
    </div>
  );
}
