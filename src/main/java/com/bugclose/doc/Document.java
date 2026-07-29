package com.bugclose.doc;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.time.LocalDateTime;

/**
 * 文档实体：项目文档归档的元信息，文件本体按版本记录在 DocumentVersion
 */
@Entity
@Table(name = "documents")
public class Document {

    /** 文档分类 */
    public enum DocCategory {
        REQUIREMENT, // 需求文档
        DESIGN,      // 设计文档
        TEST,        // 测试文档
        MANUAL,      // 操作手册
        MEETING,     // 会议纪要
        OTHER        // 其他
    }

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    /** 所属项目 ID（可空，表示未关联项目的通用文档） */
    private Long projectId;

    /** 文档名称 */
    @Column(nullable = false, length = 200)
    private String title;

    /** 分类 */
    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 20)
    private DocCategory category;

    /** 文档说明 */
    @Column(length = 1000)
    private String description;

    /** 最新版本号（从 1 递增） */
    @Column(nullable = false)
    private int latestVersionNo;

    /** 最初上传人 */
    @Column(length = 50)
    private String uploader;

    /** 创建时间 */
    @Column(nullable = false, updatable = false)
    private LocalDateTime createdAt;

    /** 更新时间（元信息编辑或新版本上传时刷新） */
    @Column(nullable = false)
    private LocalDateTime updatedAt;

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public Long getProjectId() {
        return projectId;
    }

    public void setProjectId(Long projectId) {
        this.projectId = projectId;
    }

    public String getTitle() {
        return title;
    }

    public void setTitle(String title) {
        this.title = title;
    }

    public DocCategory getCategory() {
        return category;
    }

    public void setCategory(DocCategory category) {
        this.category = category;
    }

    public String getDescription() {
        return description;
    }

    public void setDescription(String description) {
        this.description = description;
    }

    public int getLatestVersionNo() {
        return latestVersionNo;
    }

    public void setLatestVersionNo(int latestVersionNo) {
        this.latestVersionNo = latestVersionNo;
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

    public LocalDateTime getUpdatedAt() {
        return updatedAt;
    }

    public void setUpdatedAt(LocalDateTime updatedAt) {
        this.updatedAt = updatedAt;
    }
}
