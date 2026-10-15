package com.bugclose.doc;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;

/**
 * 文档数据访问
 */
public interface DocumentRepository extends JpaRepository<Document, Long>, JpaSpecificationExecutor<Document> {

    /** 统计项目下的文档数（删除项目前校验用） */
    long countByProjectId(Long projectId);
}
