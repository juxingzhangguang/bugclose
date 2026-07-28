package com.bugclose.bug;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Lob;
import jakarta.persistence.Table;

import java.time.LocalDateTime;

/**
 * Bug 实体
 */
@Entity
@Table(name = "bugs")
public class Bug {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    /** 所属项目 ID（可为空，表示未关联项目） */
    @Column(name = "project_id")
    private Long projectId;

    /** 项目内序号：每个项目独立从 1 递增，未关联项目的 Bug 自成一套序号 */
    @Column(name = "seq")
    private Long seq;

    /** 标题 */
    @Column(nullable = false, length = 200)
    private String title;

    /** 详细描述 */
    @Column(length = 4000)
    private String description;

    /** 严重程度 */
    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 20)
    private Severity severity = Severity.MEDIUM;

    /** 优先级 */
    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 20)
    private Priority priority = Priority.MEDIUM;

    /** 状态 */
    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 20)
    private BugStatus status = BugStatus.NEW;

    /** 处理人 */
    @Column(length = 50)
    private String assignee;

    /** 报告人 */
    @Column(length = 50)
    private String reporter;

    /** 图片URL列表（JSON数组字符串） */
    @Lob
    private String images;

    /** 创建时间 */
    @Column(nullable = false, updatable = false)
    private LocalDateTime createdAt;

    /** 最后更新时间 */
    private LocalDateTime updatedAt;

    public enum Severity {
        CRITICAL, HIGH, MEDIUM, LOW
    }

    public enum Priority {
        URGENT, HIGH, MEDIUM, LOW
    }

    public enum BugStatus {
        NEW, IN_PROGRESS, RESOLVED, CLOSED
    }

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

    public Long getSeq() {
        return seq;
    }

    public void setSeq(Long seq) {
        this.seq = seq;
    }

    public String getTitle() {
        return title;
    }

    public void setTitle(String title) {
        this.title = title;
    }

    public String getDescription() {
        return description;
    }

    public void setDescription(String description) {
        this.description = description;
    }

    public Severity getSeverity() {
        return severity;
    }

    public void setSeverity(Severity severity) {
        this.severity = severity;
    }

    public Priority getPriority() {
        return priority;
    }

    public void setPriority(Priority priority) {
        this.priority = priority;
    }

    public BugStatus getStatus() {
        return status;
    }

    public void setStatus(BugStatus status) {
        this.status = status;
    }

    public String getAssignee() {
        return assignee;
    }

    public void setAssignee(String assignee) {
        this.assignee = assignee;
    }

    public String getReporter() {
        return reporter;
    }

    public void setReporter(String reporter) {
        this.reporter = reporter;
    }

    public String getImages() {
        return images;
    }

    public void setImages(String images) {
        this.images = images;
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
