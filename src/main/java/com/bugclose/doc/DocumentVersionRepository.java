package com.bugclose.doc;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

/**
 * 文档版本数据访问
 */
public interface DocumentVersionRepository extends JpaRepository<DocumentVersion, Long> {

    /** 版本历史：最新在前 */
    List<DocumentVersion> findByDocumentIdOrderByVersionNoDesc(Long documentId);

    Optional<DocumentVersion> findByIdAndDocumentId(Long id, Long documentId);

    void deleteByDocumentId(Long documentId);
}
