package com.bugclose.requirement;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

/**
 * 需求仓库
 */
public interface RequirementRepository extends JpaRepository<Requirement, Long>, JpaSpecificationExecutor<Requirement> {

    /** 查询项目内当前最大序号（未关联项目的需求自成一套序号） */
    @Query("select coalesce(max(r.seq), 0) from Requirement r "
            + "where (:projectId is null and r.projectId is null) or r.projectId = :projectId")
    long findMaxSeqInProject(@Param("projectId") Long projectId);

    /** 统计项目下的需求数量 */
    long countByProjectId(Long projectId);
}
