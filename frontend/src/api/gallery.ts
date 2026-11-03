import apiClient from './client'

export interface GalleryFile {
    filename: string
    url: string
    size: number
    created_at: string
    mtime: number
    type: 'image' | 'video'
    expired: boolean
    expires_in_seconds: number | null
}

export interface GalleryResponse {
    files: GalleryFile[]
    total: number
    total_size: number
    expire_hours: number
}

export const galleryApi = {
    // Pobierz listę plików galerii
    getFiles: () =>
        apiClient.get<never, GalleryResponse>('/admin/gallery'),

    // Usuń pojedynczy plik
    deleteFile: (filename: string) =>
        apiClient.delete(`/admin/gallery/${filename}`),

    // Natychmiast wyczyść wygasłe pliki
    cleanupExpired: () =>
        apiClient.post<never, { success: boolean; deleted: number; message: string }>('/admin/gallery/cleanup'),
}
