import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React, { createRef } from 'react';
import ChatInput, { normalizeCameraFile } from '../components/ChatInput';
import Sidebar from '../components/Sidebar';

describe('TASK 2: Direct Camera Photo Capture in ChatInput', () => {
  it('renders the "Take Photo" button and hidden camera capture input with capture="environment"', () => {
    const onAttachFile = vi.fn();
    const { container } = render(
      <ChatInput
        onSendMessage={vi.fn()}
        onAttachFile={onAttachFile}
        activeFile={null}
        attachedDocuments={[]}
      />
    );

    // 1. Verify "Take Photo" button
    const cameraBtn = screen.getByRole('button', { name: /take photo/i });
    expect(cameraBtn).toBeInTheDocument();

    // 2. Verify hidden camera input with capture="environment" and accept="image/*"
    const cameraInput = container.querySelector('input[capture="environment"]');
    expect(cameraInput).toBeInTheDocument();
    expect(cameraInput).toHaveAttribute('accept', 'image/*');
    expect(cameraInput).toHaveClass('hidden');

    // 3. Verify regular file input accepts both PDFs and images
    const fileInput = container.querySelector('input[type="file"]:not([capture])');
    expect(fileInput).toBeInTheDocument();
    expect(fileInput.getAttribute('accept')).toContain('application/pdf');
    expect(fileInput.getAttribute('accept')).toContain('image/jpeg');
    expect(fileInput.getAttribute('accept')).toContain('image/webp');
  });

  it('normalizes generic camera filenames (e.g. image.jpg) to Lab_Report_Photo_YYYY-MM-DD.jpg', () => {
    const genericFile = new File(['dummy camera image'], 'image.jpg', { type: 'image/jpeg' });
    const normalized = normalizeCameraFile(genericFile);
    const today = new Date().toISOString().slice(0, 10);
    expect(normalized.name).toBe(`Lab_Report_Photo_${today}.jpg`);
  });

  it('triggers onAttachFile with normalized file when a photo is captured via the camera input', () => {
    const onAttachFile = vi.fn();
    const { container } = render(
      <ChatInput
        onSendMessage={vi.fn()}
        onAttachFile={onAttachFile}
        activeFile={null}
        attachedDocuments={[]}
      />
    );

    const cameraInput = container.querySelector('input[capture="environment"]');
    const photoFile = new File(['fake-photo-bytes'], 'image.jpg', { type: 'image/jpeg' });

    fireEvent.change(cameraInput, { target: { files: [photoFile] } });

    expect(onAttachFile).toHaveBeenCalledTimes(1);
    const attached = onAttachFile.mock.calls[0][0];
    const today = new Date().toISOString().slice(0, 10);
    expect(attached.name).toBe(`Lab_Report_Photo_${today}.jpg`);
  });

  it('clicking the "Take Photo" button triggers click on the camera input', () => {
    const chatInputRef = createRef();
    const { container } = render(
      <ChatInput
        ref={chatInputRef}
        onSendMessage={vi.fn()}
        onAttachFile={vi.fn()}
        activeFile={null}
        attachedDocuments={[]}
      />
    );

    const cameraInput = container.querySelector('input[capture="environment"]');
    const clickSpy = vi.spyOn(cameraInput, 'click');

    const cameraBtn = screen.getByRole('button', { name: /take photo/i });
    fireEvent.click(cameraBtn);

    expect(clickSpy).toHaveBeenCalledTimes(1);
  });

  it('renders attached image chip with a clean display name and camera icon', () => {
    const onDetachDocument = vi.fn();
    render(
      <ChatInput
        onSendMessage={vi.fn()}
        onAttachFile={vi.fn()}
        activeFile={null}
        attachedDocuments={[
          { id: 'img-1', name: 'Lab_Report_Photo_2026-11-14.jpg', type: 'image/jpeg' },
        ]}
        onDetachDocument={onDetachDocument}
      />
    );

    expect(screen.getByText('Lab_Report_Photo_2026-11-14')).toBeInTheDocument();
    const detachBtn = screen.getByRole('button', { name: /detach lab_report_photo_2026-11-14\.jpg/i });
    expect(detachBtn).toBeInTheDocument();
    fireEvent.click(detachBtn);
    expect(onDetachDocument).toHaveBeenCalledWith('img-1');
  });
});

describe('TASK 3: Left Sidebar Encryption Text Removed', () => {
  it('does NOT render "Encrypted at rest (Fernet) • TLS 1.3 in transit" anywhere in the sidebar', () => {
    render(
      <Sidebar
        isOpen={true}
        onToggle={vi.fn()}
        conversations={[]}
        activeId={null}
        onSelectChat={vi.fn()}
        onNewChat={vi.fn()}
        currentUser={{ id: 'u1', full_name: 'Dr. Jane Doe', email: 'jane@example.com' }}
      />
    );

    // Profile identity is rendered
    expect(screen.getByText('Dr. Jane Doe')).toBeInTheDocument();

    // Redundant security subtitle text is completely absent
    expect(screen.queryByText(/Encrypted at rest/i)).toBeNull();
    expect(screen.queryByText(/TLS 1\.3 in transit/i)).toBeNull();
    expect(screen.queryByText(/Fernet/i)).toBeNull();
  });
});
