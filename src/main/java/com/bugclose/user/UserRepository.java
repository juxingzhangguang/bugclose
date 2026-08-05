package com.bugclose.user;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.Collection;
import java.util.List;
import java.util.Optional;
import java.util.Set;

public interface UserRepository extends JpaRepository<User, Long> {

    Optional<User> findByUsername(String username);

    boolean existsByUsername(String username);

    boolean existsByUsernameAndIdNot(String username, Long id);

    /** 当前用户绑定的项目 ID 集合（普通用户数据隔离用） */
    @Query("select p.id from User u join u.projects p where u.id = :userId")
    Set<Long> findBoundProjectIds(@Param("userId") Long userId);

    long countByRoleAndEnabledTrue(User.Role role);

    /** 与给定项目集合有交集的非管理员用户（普通用户可见的协作成员） */
    @Query("select distinct u from User u join u.projects p "
            + "where u.role <> :adminRole and p.id in :projectIds")
    List<User> findCollaborators(@Param("adminRole") User.Role adminRole,
                                @Param("projectIds") Collection<Long> projectIds);
}
