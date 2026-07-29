package com.bugclose.doc;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.time.LocalDateTime;

/**
 * 文档版本实体：每次上传（首次或更新）产生一条版本记录，对应 docs 目录下一个物理文件
 */
@Entity
@Table(name = "document_versions")
public class DocumentVersion {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    /** 所属文档 ID */
    @Column(nullable = false)
    private Long documentId;

    /** 版本号（文档内从 1 递增） */
    @Column(nullable = false)
    private int versionNo;

    /** 落盘文件名（UUID.ext，避免中文名与重名问题） */
    @Column(nullable = false, length = 100)
    private String storedName;

    /** 原始文件名（下载时还原） */
    @Column(nullable = false, length = 255)
    private String originalFilename;

    /** 文件大小（字节） */
    @Column(nullable = false)
    private long fileSize;

    /** 扩展名（小写） */
    @Column(length = 10)
    private String ext;

    /** 版本更新说明 */
    @Column(length = 500)
    private String remark;

    /** 本版本上传人 */
    @Column(length = 50)
    private String uploader;

    /** 上传时间 */
    @Column(nullable = false, updatable = false)
    private LocalDateTime createdAt;

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public Long getDocumentId() {
        return documentId;
    }

    public void setDocumentId(Long documentId) {
        this.documentId = documentId;
    }

    public int getVersionNo() {
        return versionNo;
    }

    public void setVersionNo(int versionNo) {
        this.versionNo = versionNo;
    }

    public String getStoredName() {
        return storedName;
    }

    public void setStoredName(String storedName) {
        this.storedName = storedName;
    }

    public String getOriginalFilename() {
        return originalFilename;
    }

    public void setOriginalFilename(String originalFilename) {
        this.originalFilename = originalFilename;
    }

    public long getFileSize() {
        return fileSize;
    }

    public void setFileSize(long fileSize) {
        this.fileSize = fileSize;
    }

    public String getExt() {
        return ext;
    }

    public void setExt(String ext) {
        this.ext = ext;
    }

    public String getRemark() {
        return remark;
    }

    public void setRemark(String remark) {
        this.remark = remark;
    }

    public String getUploader() {
        return uploader;
    }

    public void setUploader(String uploader) {
        this.uploader = uploader;
    }

    public LocalDateTime getCreatedAt() {
        return createdAt;
    }

    public void setCreatedAt(LocalDateTime createdAt) {
        this.createdAt = createdAt;
    }
}
